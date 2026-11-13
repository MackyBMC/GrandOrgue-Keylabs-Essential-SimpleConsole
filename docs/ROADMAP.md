# Roadmap

*Status: PROPOSED. Milestones are ordered by risk (cheapest, most reversible first). Version numbers and branch names await owner acceptance (claude.chat).*

## Two tracks (ADR 0001, DECIDED)
- **v2.x (`release-2.0`)**: maintenance only. Bug-fix patches (`v2.0.9-...`). No structural change. v2.0.8 is the current release.
- **v3.x**: the framework. Evolves the existing code (ADR 0002), does not rewrite it.

## Compatibility promises (v3 vs v2)
1. Setter YAML, `.ss` projects, takes, `config.yaml` and generated GrandOrgue settings from v2 open in v3 (migrated explicitly, original backed up, GUARDRAILS I-4).
2. With the Friesach organ and a KeyLab, v3.0 behaves **identically** to v2.0.8 on the golden checks (VERIFICATION.md).
3. Existing GrandOrgue setter markers keep working.
4. The Windows installer upgrade path keeps user data.

## Milestones
| ID | Milestone | Exit criteria (all must hold) | Size |
|----|-----------|-------------------------------|------|
| M0 | **Documentation baseline and inventory pass 2** | This doc set accepted; every symbol tagged L/E/C/A/S/I; import graph and golden-file list produced; open questions in claude.chat answered. | small |
| M1 | **Safety net** | Golden-output harness for: generated GrandOrgue MIDI settings yaml, stop/coupler CC maps, LCD text frames, setter load/save round-trip, `.ss` round-trip. Runs without hardware. v2.0.8 outputs recorded as baseline. | medium |
| M2 | **Organ model as data** | `Organ` loaded from a data file; Friesach expressed as data and produces byte-identical outputs to M1 baseline; `organ_layout` globals removed from callers; Cracow loads from `odf_scan` output with no code change. | medium |
| M3 | **GrandOrgue engine adapter extracted** | `Item.path/channel/key`, `CMD_PATHS/FB_PATHS/VOLS`, ODF import, MIDI-settings generation, launcher live behind `Engine`; core has no GrandOrgue strings; M1 baseline still identical; fake engine drives core tests. | large |
| M4 | **Manuals and banks generalised** | Manual count/names from the organ; `sessionmeta.MANUALS` replaced; saved `track_map` migrated; stave works on a 2-manual and a 5-manual organ. | large |
| M5 | **KeyLab controller plugin extracted; loader** | KeyLab behaviour behind `Controller` with declared capabilities; `BridgeApp` split; manifest registry loads both plugins; controller toggle (I-2) still works; real-hardware smoke test on KeyLab + Friesach passes. **v3.0.0 candidate.** | large |
| M6 | **Aeolus standalone proof (v3.1)** | Protocol verified against the chosen Aeolus build; adapter drives notes, stops, expression, registration recall via virtual MIDI; resync works; coexistence with GrandOrgue tested (audio device). | medium |
| M7 | **Second controller (v3.2)** | One non-KeyLab controller plugin with no core change. Proves the controller seam. | medium |
| M8 | **Hosted VST3/CLAP engine (v4.x)** | Native subsystem prototype behind `Engine`; parameter learn/mapping; decision gate on JUCE vs CLAP host. Only if a real user need exists. | very large |

## Feature freeze
Between M1 and M5 no new end-user features (SCOPE.md). Bug fixes to v2 continue on `release-2.0` and are forward-ported by patch.

## Cross-cutting work items
- Import-boundary check (`tools/check_imports.py`) enforcing ARCHITECTURE section 3, from M2.
- Type cleanliness: no Pylance/pyright errors in new modules (GUARDRAILS).
- Translations: strings keyed by id, not literal GrandOrgue/KeyLab text (M5).
- Docs updated in the same patch as the change; ADRs for each contract change.

## Decision gates
- After M3: does the engine contract hold for GrandOrgue without leaks? If not, fix the contract before M4.
- After M5: release v3.0.0, then decide M6 vs M7 order by owner priority.
- Before M8: show a real user need and a maintenance plan for a native subsystem.
