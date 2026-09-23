# Third-party code in `frontend/vendor/`

Both are MIT-licensed, so they can ship inside this project as-is.

## min2phase.js

- Kociemba two-phase solver by Chen Shuang (cs0x7f).
- Taken from the MIT-vendored copy in [cubing/cubing.js](https://github.com/cubing/cubing.js)
  (`src/cubing/vendor/mit/cs0x7f/min2phase/3x3x3-min2phase.js`, commit `805dffc`).
  Upstream: <https://github.com/cs0x7f/min2phase.js>, dual GPLv3 / MIT - used here under MIT.
- Local changes are marked `cube-solver:` in the file (classic-script wrapper,
  `verbose` passed through so the phase boundary can be labelled).

```
Copyright (c) 2023 Chen Shuang

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## rubiks-cube-solver.js

- CFOP (Fridrich) solver, npm `rubiks-cube-solver` 1.2.0 by Scott McKenzie,
  <https://github.com/slammayjammay/rubiks-cube-solver>. Unmodified `lib/index.es6.js`.
- Its output uses wide turns (`d`, `r`…), slice turns (`M`, `S`) and a `prime`
  suffix. `js/engine.js` (`fromCfop`) rewrites those as plain face turns so the
  person never has to rotate the whole cube; every solution is replayed on our
  own engine before it is shown.

```
MIT License

Copyright (c) Scott McKenzie

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
