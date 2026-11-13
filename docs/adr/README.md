# Architecture Decision Records

One file per decision: context, decision, consequences, status. Statuses: ACCEPTED (owner said so), PROPOSED (awaiting owner), SUPERSEDED (link the replacement). Never edit an ACCEPTED decision silently; add a new ADR that supersedes it.

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-two-track-versioning.md) | v2.x maintenance track, v3 framework track | ACCEPTED |
| [0002](0002-evolve-not-rewrite.md) | Evolve the existing code, do not rewrite | PROPOSED |
| [0003](0003-organ-model-as-data.md) | The organ is data, not code | PROPOSED |
| [0004](0004-engine-adapter-boundary.md) | Engine adapter boundary | PROPOSED |
| [0005](0005-controller-plugin-boundary.md) | Controller plugin boundary | PROPOSED |
| [0006](0006-pure-core-and-layering.md) | Pure stdlib core and enforced layering | PROPOSED |
| [0007](0007-in-tree-plugins-first.md) | Plugins are in-tree first (frozen build constraint) | PROPOSED |
| [0008](0008-hosting-as-native-subsystem.md) | VST3/CLAP hosting as a separate native subsystem | PROPOSED |
