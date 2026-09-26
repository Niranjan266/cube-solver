"""
FastAPI backend for the cube solver.

Endpoints
---------
GET  /api/health              what the server can do right now
POST /api/scan/live           one camera frame -> grid + colours + a stability
                              signature, so the browser can auto-capture
POST /api/scan/face           one photo  -> 9 colour samples + preview boxes
POST /api/scan/cube           six photos -> a validated 54-facelet cube
POST /api/classify            54 raw colour samples -> facelets (no images)
POST /api/solve               facelets -> moves, steps, narration, 3D data
POST /api/scramble            a random cube, for trying the app without a cube
"""

from __future__ import annotations

import os
import threading
from typing import Dict, List, Optional

import numpy as np
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from cube.model import Cube, random_scramble
from cube.solver import SolveError, solve as solve_cube, warm_up
from cube.validate import CubeError, validate
import support
from vision import detect, yolo

FACE_ORDER = "URFDLB"
SITE = "https://cube.niranjand.in"       # the address search engines should use
PAGES = ["/", "/guide", "/timer", "/support"]   # the public pages, for the sitemap
INDEXNOW_KEY = "f6281d28f6fb57169945d09bead0bbd5"   # public by design (IndexNow)
FRONTEND = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

app = FastAPI(title="Rubik's Cube Solver", version="2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_tables_ready = threading.Event()


@app.middleware("http")
async def _one_address(request: Request, call_next):
    """
    Search engines should see one copy of the site. The production
    vercel.app address sends page visits to the real domain with a permanent
    redirect; other vercel.app addresses (preview builds) ask not to be
    indexed. API calls are left alone so nothing that posts data breaks.
    """
    host = request.headers.get("host", "").split(":")[0].lower()
    on_vercel = host.endswith(".vercel.app")
    if (on_vercel and host == os.environ.get("PRIMARY_VERCEL_HOST", "cube-solver-ochre.vercel.app")
            and request.method in ("GET", "HEAD") and request.url.path in PAGES + ["/manual"]):
        target = SITE + request.url.path + (("?" + request.url.query) if request.url.query else "")
        return RedirectResponse(target, status_code=301)
    response = await call_next(request)
    if on_vercel:
        response.headers["X-Robots-Tag"] = "noindex"
    return response


@app.on_event("startup")
def _startup() -> None:
    """Build the solver tables in the background so the first solve is instant."""
    def build():
        try:
            warm_up()
        finally:
            _tables_ready.set()

    threading.Thread(target=build, daemon=True).start()


# --------------------------------------------------------------------------- #
# models
# --------------------------------------------------------------------------- #

class ClassifyIn(BaseModel):
    samples: List[List[float]] = Field(
        ..., description="54 BGR triples, face order U R F D L B, reading order in a face"
    )


class SolveIn(BaseModel):
    facelets: str = Field(..., description="54 characters using the letters URFDLB")
    mode: str = Field("quick", description="'quick' (about 23 turns) or 'learn'")


class ScrambleIn(BaseModel):
    moves: int = 25


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _cube_from_facelets(facelets: str) -> Cube:
    f = "".join(facelets.split()).upper()
    if len(f) != 54:
        raise HTTPException(422, f"Expected 54 stickers, got {len(f)}.")
    bad = set(f) - set(FACE_ORDER)
    if bad:
        raise HTTPException(422, f"Unexpected letters in the cube: {sorted(bad)}")
    return Cube(f)


def _read_face(img: np.ndarray) -> Dict:
    boxes = yolo.find_grid(img)
    if boxes is not None:
        return detect.face_payload(img, boxes, "yolo", detect.sample_cells(img, boxes))
    return detect.scan_face(img)


# --------------------------------------------------------------------------- #
# endpoints
# --------------------------------------------------------------------------- #

@app.get("/api/health")
def health() -> Dict:
    return {
        "ok": True,
        "detector": "yolo" if yolo.available() else "opencv",
        "yoloStatus": yolo.status(),
        "solver": "two-phase (built in)",
        "solverReady": _tables_ready.is_set(),
        "faceOrder": list(FACE_ORDER),
        "frontend": os.path.isdir(FRONTEND),
    }


@app.post("/api/scan/live")
async def scan_live(image: UploadFile = File(...)) -> Dict:
    """One preview frame. Deliberately small and fast - called a few times a second."""
    try:
        img = detect.decode_image(await image.read(), max_side=420)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    payload = _read_face(img)
    payload.pop("quad", None)          # image-space coords are no use to the browser
    return payload


@app.post("/api/scan/face")
async def scan_face(image: UploadFile = File(...)) -> Dict:
    try:
        img = detect.decode_image(await image.read())
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return _read_face(img)


@app.post("/api/scan/cube")
async def scan_cube(
    U: UploadFile = File(...),
    R: UploadFile = File(...),
    F: UploadFile = File(...),
    D: UploadFile = File(...),
    L: UploadFile = File(...),
    B: UploadFile = File(...),
) -> Dict:
    uploads = {"U": U, "R": R, "F": F, "D": D, "L": L, "B": B}
    samples: List[List[float]] = []
    faces: Dict[str, Dict] = {}
    for f in FACE_ORDER:
        try:
            img = detect.decode_image(await uploads[f].read())
        except ValueError as exc:
            raise HTTPException(400, f"{f} face: {exc}")
        payload = _read_face(img)
        faces[f] = payload
        samples.extend(payload["samples"])
    return _classify(samples, faces)


@app.post("/api/classify")
def classify(body: ClassifyIn) -> Dict:
    if len(body.samples) != 54:
        raise HTTPException(422, f"Expected 54 samples, got {len(body.samples)}.")
    return _classify([list(map(float, s)) for s in body.samples], None)


def _is_real_cube(facelets: str) -> bool:
    try:
        validate(Cube(facelets))
        return True
    except CubeError:
        return False


def _classify(samples, faces: Optional[Dict]) -> Dict:
    # handing the validity test to the classifier lets it reject and repair
    # readings that could not have come off a real cube
    result = detect.classify(samples, is_valid=_is_real_cube)
    cube = Cube(result["facelets"])
    try:
        validate(cube)
        result["valid"] = True
        result["problem"] = None
        result["badFaces"] = []
    except CubeError as exc:
        result["valid"] = False
        result["problem"] = exc.message
        result["badFaces"] = exc.bad_faces
    if faces is not None:
        result["faces"] = faces
    return result


@app.post("/api/solve")
def solve(body: SolveIn) -> Dict:
    cube = _cube_from_facelets(body.facelets)
    try:
        return solve_cube(cube, mode=body.mode)
    except CubeError as exc:
        raise HTTPException(
            422, detail={"error": exc.message, "badFaces": exc.bad_faces}
        )
    except SolveError as exc:
        raise HTTPException(
            422,
            detail={
                "error": (
                    "That cube cannot be solved - a sticker colour was probably "
                    f"misread. ({exc})"
                ),
                "badFaces": [],
            },
        )


@app.post("/api/support")
def support_message(body: support.SupportIn, request: Request) -> Dict:
    if body.website:                       # a bot filled the hidden field: pretend it worked
        return {"ok": True}
    try:
        body = support.check(body)
    except support.SupportError as exc:
        raise HTTPException(exc.status, exc.message)
    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "")).split(",")[0]
    if support.rate_limited(ip.strip()):
        raise HTTPException(429, "That's a lot of messages. Please try again in a few minutes.")
    if not support.deliver(body):
        raise HTTPException(503, "Sorry, messages can't be sent right now. Please try again later.")
    return {"ok": True}


@app.post("/api/scramble")
def scramble(body: ScrambleIn) -> Dict:
    moves = random_scramble(max(1, min(body.moves, 60)))
    cube = Cube().apply_many(moves)
    return {"scramble": moves, "facelets": str(cube)}


# --------------------------------------------------------------------------- #
# static frontend
# --------------------------------------------------------------------------- #

if os.path.isdir(FRONTEND):
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(FRONTEND, "index.html"))

    @app.get("/manual")
    def manual():
        return FileResponse(os.path.join(FRONTEND, "index.html"))

    @app.get("/robots.txt", include_in_schema=False)
    def robots():
        # AI assistants' crawlers are welcome too: being quoted by them is the point
        ai = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot",
              "PerplexityBot", "Google-Extended", "Applebot-Extended", "Bingbot"]
        return PlainTextResponse(
            "User-agent: *\nAllow: /\nDisallow: /api/\n\n"
            + "".join(f"User-agent: {b}\nAllow: /\nDisallow: /api/\n\n" for b in ai)
            + f"Sitemap: {SITE}/sitemap.xml\n")

    @app.get("/llms.txt", include_in_schema=False)
    def llms():
        with open(os.path.join(FRONTEND, "llms.txt"), encoding="utf-8") as f:
            return PlainTextResponse(f.read(), media_type="text/markdown; charset=utf-8")

    @app.get(f"/{INDEXNOW_KEY}.txt", include_in_schema=False)
    def indexnow_key():
        # proves to Bing / IndexNow that this site asked for its pages to be re-read
        return PlainTextResponse(INDEXNOW_KEY)

    @app.get("/sitemap.xml", include_in_schema=False)
    def sitemap():
        # no <lastmod>: on Vercel every file carries the same made-up date, and
        # a wrong date is worse than none
        urls = "".join(f"<url><loc>{SITE}{p}</loc></url>" for p in PAGES)
        return Response(
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>',
            media_type="application/xml")

    @app.get("/site.webmanifest", include_in_schema=False)
    def manifest():
        return JSONResponse({
            "name": "Cube Solver", "short_name": "Cube Solver",
            "description": "Scan your Rubik's cube and follow the arrow to solve it.",
            "start_url": "/", "scope": "/", "display": "standalone",
            "background_color": "#0e1116", "theme_color": "#0e1116",
            "icons": [
                {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
                {"src": "/static/icons/icon-maskable-512.png", "sizes": "512x512",
                 "type": "image/png", "purpose": "maskable"},
            ],
        }, media_type="application/manifest+json")

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        return FileResponse(os.path.join(FRONTEND, "favicon.ico"), media_type="image/x-icon")

    @app.get("/guide")
    def guide():
        # the pre-rendered copy has the whole guide in its HTML, for crawlers
        # that do not run JavaScript (tools/prerender-guide.mjs)
        static = os.path.join(FRONTEND, "guide.static.html")
        return FileResponse(static if os.path.exists(static) else os.path.join(FRONTEND, "guide.html"))

    @app.get("/support")
    def support_page():
        return FileResponse(os.path.join(FRONTEND, "support.html"))

    @app.get("/timer")
    def timer():
        return FileResponse(os.path.join(FRONTEND, "timer.html"))
