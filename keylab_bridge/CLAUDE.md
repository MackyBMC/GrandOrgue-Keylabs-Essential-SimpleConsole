# keylab_bridge/ rules (bridge: today KeyLab + GrandOrgue, mixed; v3 splits it)
Read `docs/GUARDRAILS.md`, `docs/ARCHITECTURE.md` section 3, `docs/INVENTORY-V2.md` first.
- **No new Friesach, GrandOrgue-path, channel, CC or KeyLab-sysex constants** in `application.py` or `organ_layout.py`. New engine knowledge goes in the `go_*`/GrandOrgue-specific modules; new controller knowledge goes in the KeyLab section of `midi_protocol.py`. Mark each such constant `# E:` (engine) or `# C:` (controller) so the v3 split is mechanical.
- Do not add Qt imports to bridge logic. MIDI callbacks never touch UI state: post to the UI event queue (`post_ui_event` / `process_ui_event`).
- Do not grow `BridgeApp`; new logic goes in a small module with a narrow interface that could become part of `core`.
- Behaviour must stay byte-identical for generated GrandOrgue MIDI settings, CC maps and LCD frames unless a patch says otherwise and says why.
- Never open the KeyLab MAIN port by default (GUARDRAILS I-1). Keep DAW-port vs MAIN-port messages clearly separated.
- A controller or engine failure must not stop playback (I-2); catch at the seam and report.
- Large organs: add channels/banks, do not refuse (I-12).
