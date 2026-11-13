# ADR 0005: Controller plugin boundary
**Status:** PROPOSED.
**Context:** KeyLab specifics (DAW vs MAIN ports, sysex LCD/LED, pad CC sharing, long-press timing, LCD flood limit) are interleaved with core logic in `application.py` and `midi_protocol.py`.
**Decision:** A controller plugin translates raw MIDI to abstract `ControlEvent`s and renders abstract feedback; it declares capabilities (faders, encoders, jog, pads, LCD size, LEDs). Banking, menus and focus logic live in core and adapt to capabilities.
**Consequences:** A new controller is one plugin; core tests need only a fake controller; the KeyLab port-routing knowledge stays contained.
