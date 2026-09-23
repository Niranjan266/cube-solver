"""
Entry point for hosts that look for an ASGI app at the repository root
(Vercel's Python runtime, `uvicorn main:app`). The app itself lives in
backend/app.py and imports its packages relative to backend/.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

from app import app  # noqa: E402,F401
