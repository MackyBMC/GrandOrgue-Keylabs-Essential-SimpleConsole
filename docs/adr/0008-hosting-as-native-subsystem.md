# ADR 0008: VST3/CLAP hosting as a separate native subsystem
**Status:** PROPOSED.
**Context:** Hosting needs plugin lifecycle, audio buffers, real-time thread safety, parameter discovery and state, which Python must not do (GUARDRAILS I-1). Plugin parameters are not stops.
**Decision:** If and when needed (ROADMAP M8), build a native host (JUCE or a CLAP host) as a separate process or library behind the `Engine` contract, with a user-editable parameter learn/mapping layer. Prove the standalone-process route (Aeolus, M6) first.
**Consequences:** No immediate C++ work; the Engine contract must already allow an out-of-process engine; decision gate in ROADMAP before M8.
