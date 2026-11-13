# packaging/ rules
- Never change the v1 installer AppId or touch the `v1.0.0` tag (GUARDRAILS I-10).
- New top-level modules or v3 plugin packages must be added to the include list in `nuitka_build.py` (`--include-module` / `--include-package`); plugins are in-tree with an explicit manifest registry (ADR 0007). Verify with a frozen build, not only from source.
- Windows junctions break Inno Setup (error 448): use real paths.
- `version.py` is the single version source; tag `v<version>`; the release workflow builds Windows and experimental Linux and publishes `SHA256SUMS.txt`.
- Linux/macOS are experimental/deferred; do not claim support (I-11).
- Preserve upgrade behaviour: uninstall keeps user settings, takes and the GrandOrgue data folder.
