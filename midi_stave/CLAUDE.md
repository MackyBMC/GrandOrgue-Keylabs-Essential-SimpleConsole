# midi_stave/ rules (Stave Station: notation, piano roll, track-to-manual mapping)
Read `docs/GUARDRAILS.md`, `docs/DOMAIN-MODEL.md`, `docs/HANDOFF.md` (time bases) first.
- Must not import engine or controller code (`keylab_bridge` engine/controller parts). Depend on the organ model and a MIDI event type only.
- **Manual slots are fixed in v2 (`sessionmeta.MANUALS`, names are display only; saved `track_map` uses slot names).** Do not add more places that assume four manuals or specific channels; use the existing accessors (`manual_label`, `MANUALS`) so v3 can replace them with the organ's manuals.
- Time bases are easy to get wrong: preview file is at the average tempo; speed = session BPM / file BPM. Do not treat preview time as score seconds.
- The `.ss` project format is a compatibility surface: add fields, never rename or remove; keep older files readable (I-4).
- Stay inside scope: organ-friendly score and mapping tools, not general notation publishing or DAW editing (SCOPE.md).
- Nuitka: bare-name imports need `--include-module` in `packaging/nuitka_build.py`.
