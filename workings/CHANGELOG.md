# Changelog

Newest first. v1.0.0 and the 2026.09.24 release stay available under their own tags.

## 2.0.2-linux.1 - experimental prerelease
- Linux-only package for evaluation; it has not yet been validated on real hardware.
- Windows remains the supported stable platform; macOS is deferred until a later release.

## 2.0.1 - 2026-10-26
- Fix installed builds loading and saving setter combinations from the configured GrandOrgue data folder.
- Start GrandOrgue with the configured organ when the GUI launches.
- Include matplotlib in the Nuitka standalone build and derive installer version from the built executable.

## 2.0.0 - 2026-10-26

### New
- **Application and installer.** Compiled `KeyLabGrandOrgueBridge.exe` (Nuitka) with an Inno Setup installer. Install types: Standard or Portable (chosen in the wizard). Asks for your GrandOrgue folder (Organs / Settings / Combinations), checks for GrandOrgue and loopMIDI with download links, optional starter Combinations and MIDI settings (never overwrites). Uninstall keeps your data. Installs beside v1.0.
- **Paths.** Settings, takes and window layout live in `%APPDATA%\KeyLabGrandOrgue` (Standard), beside the exe (Portable, via `portable.flag`), or beside the scripts when run from source. `go_folder()` resolves the GrandOrgue folder from `KEYLAB_GO_FOLDER`, `go_folder.txt`, or `Documents\GrandOrgue`. A default `config.yaml` is copied on first run.
- **Release pipeline.** GitHub Actions builds Windows (stable), Linux and macOS (experimental) on a `v*` tag, writes `SHA256SUMS` and publishes the release. `version.py` is the single version source.
- **Stave Station.** MIDI to engraved score (Verovio) with: piano-roll window, voice splitting, rest tidying, fingerings and finger-substitution marks, division and coupler labels, tonic sol-fa, lyrics, title / composer / arranger credits, separate pedal staff, track selection, click-to-edit on stave areas and a stave highlighter. Original MIDI takes are kept as recorded; the stave shows the quantised version.
- **Take recorder and player** with a realtime-priority playback thread to limit latency and drift.
- **Qt interface.** Global themes (Breeze, Adwaita, Fusion, Nord and others), icon packs, polished widgets, and remembered position and size for every window and popup.
- **Developer tools.** `tools/tidy_scripts_folder.py` (dry-run archive of files the app does not need), `tools/setup_dev_repo.ps1` (clean development repository outside the GrandOrgue folder), `docs/RELEASING.md`.

### Fixed
- Selecting more than one stave no longer fails ("cannot access local variable 'el'").
- The pedal staff no longer disappears on later systems.
- Page headers are centred and no longer overlap; the "Point size <= 0" console warnings are gone.
- Composer and arranger names now appear on the score.
- Popup and secondary windows now remember where they were and how big they were.

### Changed
- Repository restructured: source now at the repository root (was `Scripts/`); the old launcher `.bat` / `.ps1` files, sniffer and LED-test scripts are removed from the tree (still available in the v1.0 tags).
- The v1 installer is kept as `packaging/v1_installer_reference.iss`.

### Known limits
- Linux and macOS packaging is experimental and untested on real machines.
- Executables are unsigned; Windows SmartScreen or antivirus may warn.
- Cross-staff stems and beaming, and a raw-versus-quantised playback buffer option, are not yet implemented.

## 2026.09.24
- Installer targets the GrandOrgue Documents workspace; checks for GrandOrgue and loopMIDI.

## 1.0.0
- First release: KeyLab Essential 61 mk2 <-> GrandOrgue bridge.
