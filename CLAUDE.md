# CLAUDE.md

Read `docs/HANDOFF.md` first: architecture, conventions, gotchas and open items. This file only holds the rules.

## Rules
- Replies short, about the actual fixes. No narration of what changed. Deliver files.
- Change notes go in the CHANGELOG block at the top of each edited source file (newest first, dated), and in `CHANGELOG.md`.
- Changes are delivered as `.patch` files made against `origin/release-2.0` (or the current dev branch). Check with `git apply --check` before delivering. Stacked patches: say the order.
- Do not commit or push unless asked. Never touch the v1.0.0 tag or v1 installer AppId.
- Do not guess about organ behaviour: say what is verified in the real app / on the real organ and what is not.
- Windows first (PowerShell, Python script mode via `python keylab_go_bridge.py`). Linux/macOS packaging is experimental.
- This is a serious, simple tool for budget churches and liturgical organ work. It is not a DAW. Do not add features that turn it into one.
