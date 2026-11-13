# Risk register

*Status: PROPOSED. Reviewed at each milestone exit. L = likelihood, I = impact (H/M/L).*

| ID | Risk | L | I | Mitigation | Owner/check |
|----|------|---|---|------------|-------------|
| R1 | **Model leakage:** GrandOrgue ids creep into "generic" data (setters, scores). | H | H | I-3/I-6; import-boundary check; logical ids only in stored data; review every new constant. | each patch |
| R2 | **No automated tests today**; large refactor can silently change behaviour. | H | H | M1 golden-output harness before any extraction; fake engine/controller. | M1 exit |
| R3 | **State desync:** a sent command does not prove the engine reached the state (Aeolus likely command-only). | M | H | shadow state, "unconfirmed" display, `resync`, capability flag `state_readback`. | M3, M6 |
| R4 | **Nuitka frozen build vs dynamic plugins.** | M | H | in-tree plugins with explicit manifest registry (ADR 0007); build test each milestone. | M5 |
| R5 | **Scope leap / DAW drift.** | H | M | SCOPE.md gate, non-goals, feature freeze, borderline register. | owner |
| R6 | **v2 data break:** user setters or projects stop opening. | M | H | I-4, migrations with backup, round-trip tests on real files (the Friesach setter set). | M2-M4 |
| R7 | **MIDI routing / driver quirks** (port sharing, loopMIDI, KeyLab DAW-mode and firmware sensitivity). | H | M | keep quirks inside the KeyLab plugin; documented recovery (HUI/Mackie reset, firmware 1.1.10); relay fallback. | M5 |
| R8 | **Audio device conflicts** with two engines (ASIO exclusivity, WASAPI, sample rates). | M | M | test early in M6; document one-engine-at-a-time fallback. | M6 |
| R9 | **Over-large organs** exceed channel/CC budget (Cracow 146 stops; more later). | M | M | I-12; channel allocation rule in the engine plugin; spill channels and banks. | M3 |
| R10 | **Single maintainer, limited session time.** | H | H | small stacked patches, docs as memory, claude.chat for questions, one change per patch. | owner |
| R11 | **Unverified claims** reach users as "works". | M | H | I-8; VERIFIED/UNVERIFIED tags; release notes list unverified items. | each release |
| R12 | **Unsigned executables** trigger SmartScreen/AV. | H | L | checksums published; signing is a later decision. | releases |
| R13 | **Linux/macOS expectations** exceed what is validated. | M | L | label experimental; no claims. | releases |
| R14 | **Aeolus protocol assumptions wrong** (CC98 scheme, channels, program change). | M | M | verify against the exact Windows build before coding (M6 entry criterion). | M6 |
| R15 | **Python-in-audio-path** creeps in via hosting work. | L | H | I-1; hosting only as separate native subsystem (ADR 0008). | M8 gate |
