# ADR 0007: Plugins are in-tree first
**Status:** PROPOSED.
**Context:** The Windows release is a Nuitka standalone build; bare-name imports require explicit `--include-module`. Free-form plugin discovery in a frozen build is fragile.
**Decision:** v3 plugins are packages inside the repo, listed in a manifest registry that the build includes explicitly. Out-of-tree third-party plugins are deferred until a tested frozen-build mechanism exists.
**Consequences:** "Plugin framework" means clean seams and contracts first, distribution later; adding a plugin requires a release; much lower packaging risk.
