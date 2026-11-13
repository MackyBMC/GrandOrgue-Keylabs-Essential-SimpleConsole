# Vision

*Status: DECIDED (owner intent, restated from the project's origin and the 2026-11-13 planning conversation).*

## Purpose
Give organists, choir directors and other church musicians an affordable, understandable, open environment for **preparing music, rehearsing, performing, controlling registrations, working with notation and recording**, without a vendor-locked console, a proprietary sound engine, or computer-specialist knowledge.

The idea dates to the late 1980s (sequencers such as Cakewalk for DOS, notation tools on the Macintosh). What was missing then, and is still missing for budget churches, is one coherent workstation built around church-music workflow rather than around a particular piece of hardware.

## The concept: a software-defined organ
Divisions, stops, couplers, tremulants, expression, registrations and performance behaviour **define the instrument**. The thing that makes the sound (GrandOrgue today; Aeolus or a VST3/CLAP instrument later) is **replaceable**. The thing the player touches (a KeyLab today; other controllers later) is **replaceable**. The musical model in the middle is the product.

```
 input controllers  <-->   BRIDGE / CORE   <-->   MIDI / audio engines
 (KeyLab, others)       (logical organ model,      (GrandOrgue, Aeolus,
                         registrations, session,    VST3/CLAP host, ...)
                         notation workflow)
```

## Who it is for
- A church organist who plays services on a sampled organ and needs registrations at hand, cued while playing.
- A choir director or accompanist who prepares hymns and scores and wants them performed through the organ with chosen registrations.
- A small church with a modest budget and no IT staff.

## Principles
1. **Design around musicians and church workflows**, not around a console or a vendor.
2. **Understandable by non-specialists.** The musician should not have to understand the machinery to use the instrument.
3. **No dependence on one sound engine, vendor or expensive hardware ecosystem.**
4. **Connect** notation, MIDI, registrations, live performance and recording in one place.
5. **Playing is sacred.** Keyboard, pedal and wheel input never depend on this software staying healthy (see GUARDRAILS I-1, I-2).
6. **Not a DAW.** Serious, simple, focused (see SCOPE.md).
7. **Honest about verification.** Nothing is claimed to work on a real organ until it has been tried on one.

## End state (the "endgame")
`input controllers <-> bridge <-> MIDI/audio engine`, where both outer ends are plugins behind stable contracts, and the engine end can eventually be a hosted VST3/CLAP instrument. v2.x is the hardcoded KeyLab-plus-GrandOrgue-plus-Friesach implementation that proves the workflow. **v3 is the framework that makes the same workflow work for any controller and any engine and any organ.**

## What success looks like (measurable)
- A second organ (e.g. the Cracow St John Cantius sample set, 146 stops) runs through the console with **no code change**, only an organ description.
- A second engine (Aeolus standalone) is driven from the same logical registrations as GrandOrgue.
- A second controller can be added by writing one controller plugin, with no change to the core.
- A volunteer organist installs it, imports an organ, and plays a service without reading source code or editing YAML by hand.
- Every v2 user file (setters, projects, settings) still opens.
