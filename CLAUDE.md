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

## Project documents (v3 planning baseline, 2026-11-13)
Start at `docs/README.md`. Before any structural change read, in order: `docs/GUARDRAILS.md`, `docs/SCOPE.md`, `docs/ARCHITECTURE.md`. Per-area rules: `keylab_bridge/CLAUDE.md`, `midi_stave/CLAUDE.md`, `packaging/CLAUDE.md`, `docs/CLAUDE.md`.

### v3 guardrails (summary; the full list is in `docs/GUARDRAILS.md`)
- Two tracks: `release-2.0` = v2 bug fixes only; v3 = controller- and engine-agnostic framework (ADR 0001). Patch names carry the version level.
- No new Friesach / GrandOrgue / KeyLab constants outside their own module; tag new ones `# E:` or `# C:`.
- Registrations and scores store logical ids, never engine paths (target design, `docs/DOMAIN-MODEL.md`).
- Core is stdlib-only; layer rule in `docs/ARCHITECTURE.md` section 3. Architectural change needs an ADR.
- Scope gate: `docs/SCOPE.md`. If a feature smells like a DAW, stop and ask.
- Mark claims VERIFIED or UNVERIFIED. The repo has no automated tests yet; do not refactor without the golden-output net (ROADMAP M1).
- Session time is limited: deliver `.patch` files, send each when ready, put questions in `docs/claude.chat/<patch-name>.txt`.
