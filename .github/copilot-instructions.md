Read CLAUDE.md first (rules), then docs/README.md (documentation map). This file only points there so Copilot, Claude Code and Claude chat follow one rule set.

Before any structural change read docs/GUARDRAILS.md, docs/SCOPE.md and docs/ARCHITECTURE.md. Architectural decisions need an ADR in docs/adr/.

Working rules (full text in CLAUDE.md):
- Deliver changes as .patch files named <level>-NN-slug.patch (v2.0.x for the release line, v3.0.0-NN for the framework). Check with `git apply --check` against the stated base. No commit or push unless asked.
- Owner questions go in docs/claude.chat/<patch-name>.txt (a "Questions" section of numbered, self-contained questions that cite repo paths). Do not ask them in chat.
- Mark claims about the real organ or hardware VERIFIED or UNVERIFIED. Not a DAW: apply the scope gate in docs/SCOPE.md.
- No new Friesach, GrandOrgue-path, channel, CC or KeyLab constants outside their own module; tag new ones `# E:` (engine) or `# C:` (controller).
- Code must be free of Pylance/pyright errors. Put a dated CHANGELOG block at the top of each edited source file and update CHANGELOG.md.
- Graph output (graphify-out/) is generated and git-ignored: never commit it, and treat it as a hint only; the docs above decide intent.

## graphify

For any question about this repo's architecture, structure, components, or how to add/modify/find
code, your first action should be `graphify query "<question>"` when `graphify-out/graph.json`
exists. Use `graphify path "<A>" "<B>"` for relationship questions and `graphify explain "<concept>"`
for focused-concept questions. These return a scoped subgraph, usually much smaller than the full
report or raw grep output.

Triggers: "how do I…", "where is…", "what does … do", "add/modify a <component>",
"explain the architecture", or anything that depends on how files or classes relate.

If `graphify-out/wiki/index.md` exists, use it for broad navigation. Read `graphify-out/GRAPH_REPORT.md`
only for broad architecture review or when query/path/explain do not surface enough context. Only read
source files when (a) modifying/debugging specific code, (b) the graph lacks the needed detail, or
(c) the graph is missing or stale.

Type `/graphify` in Copilot Chat to build or update the graph.
