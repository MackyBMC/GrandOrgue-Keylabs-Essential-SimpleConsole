# Third-party software

This application is MIT-licensed (see LICENSE). It uses and may bundle the components below under their own licences. Entries marked **verify** have not been confirmed against the shipped files.

## Bundled or imported at run time
| Component | Licence | Used for | Notes |
|---|---|---|---|
| Qt for Python (PySide6, shiboken6) | LGPL-3.0-only (also offered under GPL or commercial terms) | GUI | Dynamically linked. Release builds are a standalone folder (not onefile), so the Qt libraries stay separate files that the user can replace. Modules used: QtCore, QtGui, QtWidgets, QtSvg, QtSvgWidgets, QtPdf, QtPdfWidgets, QtPrintSupport. Qt PDF is available under LGPL-3.0, GPL-2.0 or commercial terms (Qt 6.8 licensing page). It includes a PDFium snapshot, so these notices also apply: PDFium (BSD), Chromium project (BSD-3-Clause), Abseil (Apache-2.0), FreeType (FreeType Licence: asks for credit), fast_float (MIT), ICU (MIT), libjpeg-turbo (IJG, BSD-3, Zlib: IJG asks for credit), libpng (libpng licence), zlib (Zlib). |
| Verovio | LGPL-3.0-only (COPYING and COPYING.LESSER ship in the wheel) | Score engraving | Separate library file in the standalone build, replaceable. Verovio's licensing page allows commercial use, open source or not, if the library is unmodified and dynamically linked, and **asks for visible credit to Verovio**; modifications must be published under LGPL-3.0. The bundled music fonts (Bravura, Gootville, Leipzig, Leland, Petaluma) are not covered by that page and the wheel carries no font licence files: **verify** each before a commercial release. |
| music21 | BSD-3-Clause | Notation model | Its package data includes a corpus (about 3,200 files) distributed with the permission of the encoders; the music21 corpus notice says some encodings may not be used commercially (for example the Essen folksong collection is cleared for non-commercial use only). The build currently includes all of music21's package data. See "Open items". music21 also ships a Scala scale collection with its own licence file. |
| mido | MIT | MIDI files and messages | |
| python-rtmidi | MIT (includes RtMidi) | MIDI ports | |
| PyYAML | MIT | Configuration and setter files | |
| qtawesome | MIT | Icons | Icon fonts: Material Design Icons (Apache-2.0), Phosphor (MIT), Remix Icon (Apache-2.0), Font Awesome Free (icons CC BY 4.0, fonts OFL 1.1). Attribution is required for Font Awesome and the Apache-2.0 sets. |
| textual | MIT | Terminal console | |
| numpy | BSD-3-Clause (with 0BSD, MIT, Zlib and CC0 parts) | Audio visuals (optional) | |
| PyAudioWPatch | Apache-2.0 (PortAudio is MIT-style) | Windows audio capture (optional) | |
| pycaw | MIT | Windows per-program volume (optional) | |

## Reference project
The KeyLab LCD frame format and LED numbers were informed by studying Ray Juang's flstudio-arturia-keylab-mk2 project (https://github.com/rjuang/flstudio-arturia-keylab-mk2). Its licence text, reproduced as that licence requires for derived material:

> MIT License
>
> Copyright (c) 2020 Ray Juang
>
> Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

## Build and packaging tools (not shipped)
Nuitka (AGPL-3.0; its documentation states that compiled output is not covered by the AGPL: **verify** for releases), Inno Setup 6, GitHub Actions.

## Not distributed with this application
- GrandOrgue (GPL): run as a separate program; no GrandOrgue code is included.
- The Friesach Parish Church sample set (Piotr Grabowski): obtained separately under its own terms.
- Aeolus (planned engine; GPL as far as known): to be run as a separate program, never bundled. **verify** before any integration.

## Open items
1. music21 corpus (owner decision 2026-11-16): v2 keeps the build as is; **v3 builds must exclude the corpus** (some bundled encodings are non-commercial only). The application only parses the user's own files. Test a build without it first. The Scala scale collection has its own licence file: check it too.
2. Verovio music fonts: confirm the licence of Bravura, Gootville, Leipzig, Leland and Petaluma (neither Verovio's licensing page nor the wheel states them) before the v3 release.
3. Credits and licence texts to ship (About / Licences screen or a `licenses/` folder): visible Verovio credit; FreeType and IJG acknowledgements; Apache-2.0 notices (Material Design Icons, Remix, Abseil, PyAudioWPatch); Font Awesome CC BY 4.0 attribution; full LGPL-3.0 text; the reference project's MIT notice above.
4. Nuitka: confirm from its documentation that compiled output is not covered by the AGPL.
