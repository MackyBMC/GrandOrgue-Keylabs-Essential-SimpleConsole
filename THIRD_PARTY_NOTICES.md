# Third-party software

This application is MIT-licensed (see LICENSE). It uses and may bundle the components below under their own licences. Entries marked **verify** have not been confirmed against the shipped files.

## Bundled or imported at run time
| Component | Licence | Used for | Notes |
|---|---|---|---|
| Qt for Python (PySide6, shiboken6) | LGPL-3.0-only (also offered under GPL or commercial terms) | GUI | Dynamically linked. Release builds are a standalone folder (not onefile), so the Qt libraries stay separate files that the user can replace. Modules used: QtCore, QtGui, QtWidgets, QtSvg, QtSvgWidgets, QtPdf, QtPdfWidgets, QtPrintSupport. Qt's current licensing page lists no GPL-only module among these; **verify** QtPdf against the licence file shipped in the PySide6 add-ons package. |
| Verovio | LGPL-3.0-only (COPYING and COPYING.LESSER ship in the wheel) | Score engraving | Separate library file in the standalone build, replaceable. It bundles music fonts (Bravura, Gootville, Leipzig, Leland, Petaluma) with their own licences: **verify** each before a commercial release. |
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
The KeyLab LCD frame format and LED numbers were informed by studying Ray Juang's flstudio-arturia-keylab-mk2 project (https://github.com/rjuang/flstudio-arturia-keylab-mk2), which is MIT-licensed. Its copyright notice is reproduced here if any of its code or data was derived: **verify and copy the exact copyright line from that project's LICENSE file.**

## Build and packaging tools (not shipped)
Nuitka (AGPL-3.0; its documentation states that compiled output is not covered by the AGPL: **verify** for releases), Inno Setup 6, GitHub Actions.

## Not distributed with this application
- GrandOrgue (GPL): run as a separate program; no GrandOrgue code is included.
- The Friesach Parish Church sample set (Piotr Grabowski): obtained separately under its own terms.
- Aeolus (planned engine; GPL as far as known): to be run as a separate program, never bundled. **verify** before any integration.

## Open items
1. Decide whether builds should exclude the music21 corpus (the application calls `converter.parse` on the user's own files; nothing in the code uses the corpus). Test a build without it before changing the Nuitka options.
2. Confirm the licences of the Verovio fonts and of QtPdf.
3. Copy the reference project's exact copyright line.
4. Ship the full licence texts (LGPL-3.0, Apache-2.0, OFL, CC BY 4.0) in an About / Licences screen or a `licenses/` folder of the installer.
