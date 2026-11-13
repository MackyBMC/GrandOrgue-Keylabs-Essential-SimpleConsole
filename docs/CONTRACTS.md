# Plugin contracts

*Status: PROPOSED. Signatures are a specification sketch in Python typing notation, to be refined in ROADMAP M2/M4. They are not yet code. Contracts are versioned (`CONTRACT_VERSION`); a plugin declares the version it targets.*

## Common rules
- Plugins live in-tree and register through a manifest (ADR 0007).
- Plugins never import each other or `app`. They import `contracts` and `core` only.
- All plugin callbacks into core are **thread-safe enqueue calls**; core processes on the UI/event thread (I-7).
- A plugin never raises into core: errors are reported through `report_error(...)` and the plugin enters a `FAILED` state; core keeps running (I-2).
- Capabilities are declared up front and queried by core; core degrades, never assumes.

## Manifest
```yaml
id: grandorgue
kind: engine            # engine | controller
version: 1.0.0
contract: 1
display_name: GrandOrgue
platforms: [windows, linux]
capabilities: {...}     # kind-specific, see below
entry: plugins.engines.grandorgue:Plugin
```

## Controller contract
```python
class Controller(Protocol):
    manifest: Manifest
    capabilities: ControllerCapabilities   # faders:int, encoders:int, jog:bool, pads:int,
                                           # lcd:(cols,rows)|None, leds:bool, daw_mode:bool
    def open(self, host: ControllerHost) -> None: ...   # connect ports; host.emit(ControlEvent)
    def close(self) -> None: ...                        # idempotent; safe if device is gone
    def set_text(self, lines: Sequence[str]) -> None: ...
    def set_led(self, control: ControlRef, state: LedState) -> None: ...
    def set_bank_view(self, view: BankView) -> None: ...  # optional per capability
    def status(self) -> PluginStatus: ...               # DISCONNECTED | READY | FAILED(reason)
```
`ControlEvent(kind, index, value, source, t)` where `kind` is one of `NAV_LEFT, NAV_RIGHT, JOG_TURN, JOG_PRESS, FADER, ENCODER, PAD, TRANSPORT_*, MENU_TOGGLE, ...`. The v2 KeyLab behaviours (DAW vs MAIN port separation, Cat/Char override, long-press, pad 4/5 shared CC, LCD flood limit, LED refresh) are **entirely inside** the KeyLab plugin.

## Engine contract
```python
class Engine(Protocol):
    manifest: Manifest
    capabilities: EngineCapabilities   # state_readback:bool, expression:bool, registration_steps:bool,
                                       # max_controls:int|None, transport:bool, audio_capture:bool
    def start(self, host: EngineHost, organ: Organ) -> None: ...   # launch/attach, build wire map
    def stop(self) -> None: ...
    def load_organ(self, organ: Organ) -> LoadResult: ...
    def import_organ(self, source: Path) -> OrganImport: ...       # e.g. ODF scan -> Organ + wire map
    def set_control(self, ref: LogicalRef, on: bool) -> None: ...  # stop / coupler / tremulant
    def set_expression(self, division: str, value: float) -> None: ...
    def recall_registration(self, reg: Registration) -> None: ...
    def transport(self, cmd: TransportCmd) -> None: ...            # play/stop/loop/metronome/panic/tempo
    def resync(self) -> None: ...                                  # force engine to the core's state
    def status(self) -> PluginStatus: ...
```
Engine to core, through `EngineHost`: `state_changed(ref, on)`, `step_changed(n)`, `file_loaded(name)`, `error(...)`. If `state_readback` is false the adapter keeps shadow state and core shows "unconfirmed" instead of "confirmed".

## Capability-driven behaviour (examples)
| Core feature | Needs | If missing |
|--------------|-------|------------|
| Confirmed stop state on LCD/LEDs | engine `state_readback` | show last-sent state, mark unconfirmed, offer Resync |
| Fader banks | controller `faders>0` | other controls (jog list); no bank paging |
| 4-char LCD status + scroll messages | controller `lcd` | skip; GUI shows it |
| Registration steps `<<` `>>` | engine `registration_steps` | core steps through stored steps by recalling full registrations |
| >127 controls | engine `max_controls` | adapter allocates extra channels/banks (I-12) |

## Compatibility and versioning
Contract changes follow semantic versioning: additive = minor; breaking = major with a migration note in an ADR. A plugin targeting an unsupported contract is refused with a clear message, not loaded half-way.

## Conformance testing
Each contract has a **fake counterpart** (fake engine records commands; fake controller emits scripted events) used by core tests, and a **conformance suite** a plugin must pass without hardware (lifecycle, idempotent close, error isolation, capability honesty). Hardware checks stay manual (VERIFICATION.md).
