---
applyTo: "**"
---
# Patch workflow and the claude.chat procedure (always follow)

The owner applies and commits. You deliver patches and notes; you never commit or push. Claude chat works the same way, so the two of you must produce patches that stack.

## Patches
1. Name: `v<version>-NN-slug.patch` (NN = apply order inside that version, e.g. `v2.0.9-03-fix-x.patch`). A fix to an applied patch is a new, higher-numbered patch; never re-send an applied one.
2. Base: state the commit hash in the companion note. Before delivering, `git fetch` and rebuild against the latest `origin/release-2.0` (or the current dev branch) plus any patches the owner has told you are applied. Run `git apply --check` against that state and report pass/fail.
3. One editor per file: if another pending patch (yours or Claude chat's) touches the same file, say so and wait for the owner to commit it, then rebuild.
4. Keep hunks small: `git diff -U1`. Put the CHANGELOG.md line in its own hunk, away from code, so parallel patches do not clash. Each edited source file also gets a dated CHANGELOG block (newest first) at its top.
5. Checks to state in the note: `git apply --check`, `python -m py_compile`, Pylance/pyright clean (guard `str | None`, type optional libraries, no nested same-type quotes inside f-strings). Mark anything not run UNVERIFIED. Behaviour on the real app / organ is UNVERIFIED unless the owner confirmed it.
6. If a patch fails to apply, rebuild it against the current files; do not tell the owner to edit by hand.
7. Patches, companion notes and answers are devops files: keep them out of commits (they are git-ignored). Leave the working tree free of source changes after generating a patch.

## claude.chat folder (owner questions and answers)
- Questions: `docs/claude.chat/<patch-name>.txt`. Layout: first line `<patch-name>.patch  (files touched; base <hash>)`, one paragraph of what the patch does, then `Questions` (numbered, each self-contained, citing repo paths, with a default answer) and `Notes`. Do not ask the owner questions in chat.
- Answers: the owner's tool writes `docs/claude.chat/answers/<patch-name>.answers.txt`:
  `ANSWERS-FOR: <patch-name>.txt`, `SAVED: <date time>`, `FORMAT: 1`, then per question `Qn:` text, `An:` YES / NO / DISCUSS / (none), optional `Nn:` free-text notes. Read the answers file before the next patch on that topic; a DISCUSS or a note changes the plan.
- A new patch on a topic folds in all earlier answers for it and says so in its question file.
- New files under docs/claude.chat/ are ignored by git: when one must be tracked, tell the owner to use `git add -f`.

## Companion note for every patch (same name, `.txt`)
Status, patch name, base commit, what changed (2-4 lines), checks run and their result, anything UNVERIFIED, and the open questions (pointing at the claude.chat file).
