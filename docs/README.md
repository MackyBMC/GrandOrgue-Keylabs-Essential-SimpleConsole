# Documentation map

Single entry point for the SimpleConsole (KeyLab GrandOrgue Bridge) documentation set.
Status of this set: **v3 planning baseline, 2026-11-13.** Written against `release-2.0` @ `94fea73`.

## Read order
| # | Document | Answers | Audience |
|---|----------|---------|----------|
| 1 | [VISION.md](VISION.md) | Why does this exist, for whom, what does "done" look like? | everyone |
| 2 | [SCOPE.md](SCOPE.md) | What is in, out, and deferred? How do I decide whether a feature belongs? | owner, contributors, assistants |
| 3 | [GUARDRAILS.md](GUARDRAILS.md) | Which rules must never be broken? | everyone, assistants first |
| 4 | [ARCHITECTURE.md](ARCHITECTURE.md) | How is it structured (now and in v3)? What may depend on what? | developers |
| 5 | [DOMAIN-MODEL.md](DOMAIN-MODEL.md) | What do the words mean? What is the logical organ? | everyone |
| 6 | [CONTRACTS.md](CONTRACTS.md) | What exactly must a controller / engine plugin provide? | plugin authors |
| 7 | [INFRASTRUCTURE.md](INFRASTRUCTURE.md) | Ports, channels, files, build, release, platforms, dependencies | developers, packagers |
| 8 | [INVENTORY-V2.md](INVENTORY-V2.md) | Where is the hardcoding today, and where does each piece go? | migration work |
| 9 | [ROADMAP.md](ROADMAP.md) | Milestones, exit criteria, compatibility promises | owner |
| 10 | [RISKS.md](RISKS.md) | What could go wrong and what is the mitigation? | owner |
| 11 | [VERIFICATION.md](VERIFICATION.md) | What is proven, what is not, how do we test? | everyone |
| - | [adr/](adr/) | One file per architectural decision, with status | developers |
| - | [HANDOFF.md](HANDOFF.md), [NEXT-SESSION.md](NEXT-SESSION.md) | v2.0.x working notes (current release line) | assistants |
| - | `claude.chat/` | Per-patch notes and open questions for the owner | owner |

Per-area rules for assistants live next to the code: `CLAUDE.md` (root), `keylab_bridge/CLAUDE.md`, `midi_stave/CLAUDE.md`, `packaging/CLAUDE.md`, `docs/CLAUDE.md`.

## Status tags (used in every document)
- **DECIDED**: the owner has said so. Changing it needs the owner.
- **PROPOSED**: recommended design, awaiting owner acceptance. Do not build irreversible work on it.
- **OPEN**: a question that blocks a decision.
- **VERIFIED**: observed in the real application on the real organ / hardware (state where and when).
- **UNVERIFIED**: believed from code reading or documentation only.

## Document history
| Date | Change |
|------|--------|
| 2026-11-13 | Initial v3 planning set (vision, scope, guardrails, architecture, domain model, contracts, infrastructure, v2 inventory, roadmap, risks, verification, ADR 0001-0008, per-area CLAUDE.md files). |
