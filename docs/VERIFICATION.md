# Verification

*Status: VERIFIED/UNVERIFIED lists are taken from README "Tested setup / Known limits" and docs/NEXT-SESSION.md at `release-2.0` @ `94fea73`. The test strategy is PROPOSED.*

## 1. What is proven
Tested setup (VERIFIED by the owner, one setup): GrandOrgue v3.17.3-1, Arturia KeyLab Essential 61 mk2 firmware 1.1.10 in DAW mode, Windows 11, Python 3.13 from source, loopMIDI `GO2Bridge`/`Bridge2GO`, Friesach Parish Church sample set. The v2.0.8 Windows release is "supported; see the release notes".

## 2. What is not proven (carry into release notes)
- Live audio capture, knob drags setting volumes, cue preview, pedal page turns, pedal-low split, playback timing, gate events (audition) on the real organ (NEXT-SESSION open list).
- Jog/sustain activation that "switches then reverts"; only TRACE-instrumented.
- Main-window Tempo % reportedly without effect; note-timing jitter on Windows after the `Condition.wait` change; GrandOrgue tempo may stall at its limits.
- Linux end-to-end (MIDI routing, hardware); macOS entirely.
- Any organ other than Friesach (Cracow scan exists; mapping not verified in GrandOrgue).
- `LED_IDS["cat_char"]` sysex id (UNVERIFIED on hardware, per the code comment).
- Aeolus protocol details (CC98 scheme etc.) against a specific build.

## 3. The gap: no automated tests
The repo contains no test suite (no `tests/` directory, no `test_` functions in the tree). Refactoring 21k lines without a net is the main technical risk (RISKS R2). M1 builds the net first.

## 4. Test strategy (PROPOSED)
| Level | What | Needs hardware? |
|-------|------|-----------------|
| Golden files | Generated GrandOrgue MIDI settings yaml, CC/channel maps, LCD frames, setter and `.ss` round-trips recorded from v2.0.8; v3 must match byte for byte (or via a documented, reviewed diff). | no |
| Core unit tests | Organ model, registrations, banks, tempo, state machines (focus/menu/long-press) on pure Python. | no |
| Contract conformance | Each plugin passes lifecycle, idempotent close, error isolation, capability honesty against fake host. | no |
| Adapter tests | Engine/controller adapters against fake MIDI ports and recorded sniffer captures (the KeyLab DAW-mode captures already exist as logs). | no |
| Import boundary | AST check enforcing the layering rule. | no |
| Real-organ checklist | Fixed list run before each release: install, import organ, setters cue/activate, banks, volume, transport, take record/play, controller toggle, port loss recovery. | **yes** |
| Hardware smoke (controller) | Buttons, jog, faders, encoders, pads, LCD, LEDs on the KeyLab. | **yes** |

## 5. Definition of done (any patch)
1. Applies cleanly (`git apply --check`) on the stated base.
2. No Pylance/pyright errors in changed files.
3. Golden outputs unchanged, or the diff is explained and approved.
4. CHANGELOG block in each edited source file and `CHANGELOG.md` updated; docs updated if a contract, invariant or file location changed.
5. Release notes state what is VERIFIED on the real organ and what is not.
