# ADR 0004: Engine adapter boundary
**Status:** PROPOSED.
**Context:** `Item.path` builds GrandOrgue object paths inside the logical model; channel/CC allocation and object paths are spread over `organ_layout`, `midi_protocol`, `application`.
**Decision:** Everything that knows an engine's addressing (paths, CCs, channels, process launch, settings generation, feedback parsing) lives in that engine's plugin behind the `Engine` contract (CONTRACTS.md). Engines declare capabilities; core degrades gracefully. Command-only engines get shadow state plus `resync`.
**Consequences:** `Item` loses wire fields; golden files guard the GrandOrgue output; a second engine (Aeolus) becomes a plugin, not a fork.
