# Deployment / venv follow-up (2026-11-10)

This note covers changes made **after** `v2.0.6-timing-lcd-float.patch` (the LCD enhancements, MIDI timing, and score-follow/visual-cue fixes). It is for the next assistant/developer; it does not replace `docs/HANDOFF.md`.

## Follow-up patch

`v2.0.6-deploy-venv.patch` is a second, stacked patch. Apply it **after** `v2.0.6-timing-lcd-float.patch` on a clean `release-2.0` base.

It updates `tools/deploy_dev.ps1` so:

- Robocopy preserves `.venv` and `.venv-build` in the target rather than copying over them from the source.
- `-Pip` targets `$Target\.venv-build\Scripts\python.exe` and installs the source `requirements.txt` there. It uses the repository `.venv-build` Python as the pip frontend (falling back to PATH Python) with pip's `--python` option, and reports missing interpreter/requirements or pip failures.
- `-Run` starts `keylab_go_bridge.py` with the target venv interpreter instead of PATH Python.
- The script and top-level changelog document this behavior.

The follow-up passed `git apply --reverse --check` against the current tree. The PowerShell script parsed successfully. The original feature patch is already applied in the current worktree; do not apply it a second time here.

## Live deployment changes (outside Git)

Target folder: `H:\Users\bmche\Documents\GrandOrgue\Scripts`.

- Updated the live `start_keylab_bridge.ps1` to prefer `Scripts\.venv-build\Scripts\python.exe`; it retains the existing PATH `python` / `py` fallback if that venv interpreter is absent.
- `start_keylab_grandorgue.ps1` and the desktop shortcut command were not changed. The wrapper sets `FORCE_PY=1` and invokes `start_keylab_bridge.ps1`, so it now reaches the target venv through the updated inner launcher.
- These launcher scripts are not tracked in the current repository source tree. The live launcher edit is therefore not included in `v2.0.6-deploy-venv.patch`; preserve it separately if rebuilding/recreating the deployment folder.

## Deployed venv repair

The target venv is Python 3.13 at `Scripts\.venv-build\Scripts\python.exe`.

- Installed `numpy 2.5.4` and `PyAudioWPatch 0.2.12.9` into that venv.
- Its own `pip` was damaged (`pip._vendor.packaging` missing); `ensurepip --upgrade` reported pip already present and did not repair it. Used the healthy repository venv's pip with `--python <target-python>` instead.
- The target had `packaging` metadata but an incomplete module (import produced an empty namespace). Force-reinstalled `packaging` into the target venv with the same pip frontend.
- Verified imports for `packaging`, `mido`, `rtmidi`, `PySide6`, `yaml`, `textual`, `numpy`, and `pyaudiowpatch`. No GUI launch or real MIDI/organ test was performed.

## Next deployment

Use `deploy_dev.ps1` with `-Pip` to install the full current requirements into the target venv; add `-Run` if the bridge should launch after deployment. The desktop shortcut itself does not need a path change as long as the live bridge launcher remains updated.
