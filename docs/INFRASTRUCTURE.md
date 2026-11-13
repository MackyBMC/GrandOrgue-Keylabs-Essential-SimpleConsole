# Infrastructure map

*Status: VERIFIED from code, README and workflow files on `release-2.0` @ `94fea73`, except where tagged UNVERIFIED. Hardware/organ behaviour is only as verified as VERIFICATION.md says.*

## 1. Runtime topology (Windows, default)
```
KeyLab DAW port  ->  Bridge (this app)  ->  loopMIDI "Bridge2GO"  ->  GrandOrgue
KeyLab LCD/LEDs  <-  Bridge             <-  loopMIDI "GO2Bridge"  <-  GrandOrgue feedback
KeyLab MAIN port ------------------------------------------------->  GrandOrgue   (keys, pedal, wheels, direct)
```
- GrandOrgue enables the KeyLab **MAIN** input and the virtual cable (in and out). The KeyLab **DAW** input stays **disabled** in GrandOrgue (its button messages are ordinary notes and would sound pipes).
- The bridge does not open MAIN by default so GrandOrgue keeps it. Pads need MAIN: use a splitter/shared input, or the **relay** (`relay_main_out`/`relay_main_in`) where the driver refuses sharing.
- Virtual MIDI: loopMIDI on Windows. Linux: RtMidi (ALSA/JACK) endpoints must exist; the Linux build does not create them (UNVERIFIED end-to-end).

## 2. MIDI channel plan (1-based channels)
| Channel | Use | Source |
|---------|-----|--------|
| 1 | KeyLab keyboard channel (set back to 1 after the MCC reset) | owner log |
| 2-5 | Manual slots: Pedal, Hauptwerk, Schwellwerk, Solowerk (`sessionmeta.MANUALS`, `manual_channels` override) | HANDOFF.md |
| 6-9, 11, 13 | Spill channels for organs with more than 127 controls (`DEFAULT_SPILL_CHANNELS = [13, 11, 9, 8, 7, 6]`, tried in that order) | `organ_layout.py` |
| 12 | Volume levels, bridge to GrandOrgue (`VOL_CH = 11`, 0-based) | `midi_protocol.py` |
| 14 | Feedback, GrandOrgue to bridge | README |
| 15 | Stop / coupler / tremulant CCs (`STOP_CHANNELS = [15]`, 127 controls each) | `organ_layout.py` |
| 16 | Command messages | README |
All of this is **engine- and organ-specific** and moves into the GrandOrgue plugin and the organ's wire map in v3. Check generated spill channels against channels already in use (manual input, volume, feedback, commands) when mapping large organs such as Cracow (UNVERIFIED; the channel-allocation rule belongs in the GrandOrgue plugin).

## 3. Ports and names
| Setting (`config.yaml`) | Default | Purpose |
|-------------------------|---------|---------|
| `ports.go` / `ports.go_out` | `GO2Bridge` / `Bridge2GO` | virtual cable, both directions |
| `ports.keylab_in` | `DAW` | buttons, jog, faders, encoders |
| `ports.keylab_out` | `KeyLab` | LCD and LEDs (try `DAW` if blank) |
| `ports.keylab_main_in` | `Ess Midi In` | pads |
| `ports.relay_main_out/in` | blank | MAIN relay fallback |
Names are matched as case-insensitive substrings. `python keylab_go_bridge.py --list` shows what is visible.

## 4. Files and folders
| What | Windows | Notes |
|------|---------|-------|
| Per-user data (settings, takes, layout) | `%APPDATA%\KeyLabGrandOrgue` | Linux `~/.config/KeyLabGrandOrgue`, macOS `~/Library/Application Support/KeyLabGrandOrgue` |
| Portable mode | folder of the program, marked by `portable.flag` | config, takes beside the program |
| GrandOrgue folder (Organs, Settings, Combinations) | chosen in installer, stored in `go_folder.txt` (owner's is on `H:`) | must be configurable for other users' installs |
| Organ files | e.g. `C:\Audio\Sound Samples\GrandOrgue\...\*.organ` | `organ_path` in `config.yaml` |
| Setter files | `<GO folder>\Combinations\<organ>\*.yaml` | one file per registration/piece |
| GrandOrgue MIDI settings | `<GO folder>\Settings\<organ> ... midi import.yaml` | generated; merge, do not import over (README) |
| Stave project | `<midi name>.ss` (YAML) beside the MIDI | links MIDI by relative path, absolute path, size, SHA-1 |
| Source checkout | repo root | `KEYLAB_GO_FOLDER` env var or `go_folder.txt` for the dev organ folder |

## 5. Build, release, environments
- **Source run:** Python 3.11+, `pip install -r requirements.txt`, `python keylab_go_bridge.py`.
- **Build:** `packaging/nuitka_build.py` (Nuitka standalone). Bare-name imports need `--include-module`; `keylab_bridge` is `--include-package`; matplotlib excluded.
- **Windows installer:** Inno Setup 6 (`packaging/installer.iss`), Standard and Portable modes, GrandOrgue-folder page. Keep the v1 installer AppId untouched (GUARDRAILS I-10). Junctions break Inno (error 448): use real paths.
- **CI/CD:** `.github/workflows/release.yml`. Push tag `v*` builds Windows and experimental Linux (Python 3.12, ubuntu-22.04), uploads artifacts, publishes a GitHub Release with `SHA256SUMS.txt`. Tag `v*-linux.*` builds Linux only. macOS deferred. Executables unsigned (SmartScreen warnings expected).
- **Versioning:** `version.py` is the single source (`APP_VERSION`); bump, tag, push.
- **Branches:** `release-2.0` is the v2 line (v2.0.8 released). v3 branch strategy: OPEN (claude.chat).
- **Dev tooling:** `tools/` (`check_env.py`, deploy scripts), VS Code tasks, Copilot/Claude guidance files. There is **no automated test suite** in the repo (VERIFICATION.md).

## 6. Dependencies and the layer allowed to use them (v3 target)
| Dependency | Used for | Allowed in |
|------------|----------|------------|
| stdlib | everything | all layers; **only** thing core may use |
| mido, python-rtmidi | MIDI I/O, files | plugins, app edge, `stave` file I/O (via event type at the boundary) |
| PyYAML | data files | `core.io` edge / app; not core logic |
| PySide6, qtawesome | GUI | app, stave UI |
| music21, verovio | notation, engraving | stave |
| textual | terminal UI | app (retire/maintain: OPEN) |
| numpy, PyAudioWPatch | optional audio visuals | app, optional |
| pycaw | optional per-program volume (Windows) | app, optional |

## 7. Platform matrix
| Platform | Status |
|----------|--------|
| Windows 10/11 | Supported (v2.0.8). Tested on one KeyLab/Windows setup. |
| Linux | Experimental package; routing and hardware not validated. X11 recommended for GrandOrgue. |
| macOS | Not released. |
