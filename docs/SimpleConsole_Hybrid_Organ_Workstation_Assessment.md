# SimpleConsole and the Hybrid Organ Workstation

## Conversation summary, intent, links and technical assessment

**Prepared:** 13 November 2026\
**Main project:**
https://github.com/MackyBMC/GrandOrgue-Keylabs-Essential-SimpleConsole

## 1. Purpose and origins

The project grew from an idea dating to the late 1980s. Early music
software such as Cakewalk for DOS showed the potential of computer-based
sequencing, while Macintosh notation and score tools demonstrated other
possibilities. The gap was a coherent, approachable music workstation
designed around the needs of church musicians.

The long-term aim is to give organists, choir directors and other church
musicians an affordable, understandable and open environment for
preparing music, rehearsing, performing, controlling registrations,
working with notation and recording.

The guiding principles are: - Design around musicians and church-music
workflows, not a particular hardware console. - Keep the application
understandable to users who are not computer specialists. - Avoid
dependence on one proprietary sound engine, vendor or expensive hardware
ecosystem. - Connect notation, MIDI, registrations, live performance and
recording. - Do not let the project become a general-purpose DAW.

The broader concept is a **software-defined organ**: divisions, stops,
couplers, registrations and performance behaviour define the musical
instrument; the sound engine that produces the audio is replaceable.

## 2. Existing foundation

The application is a Python/PySide6 desktop project with substantial
work already directed at: - Arturia KeyLab control-surface
integration. - Organ divisions, stops, banks and MIDI mappings. -
Registration/setter management. - MIDI playback and recording-related
workflows. - Stave/notation workflows and MIDI/MusicXML handling. -
Piano-roll editing and track/manual assignment. - Desktop GUI functions.

The conversation identified useful existing structures, including `Item`
in `keylab_bridge/organ_layout.py` and registration/marker handling in
`midi_stave/sessionmeta.py`.

These are meaningful foundations, but the current model was assessed as
**organ-aware rather than fully engine-independent**.
GrandOrgue-specific object paths, switch mappings and organ assumptions
need to be separated from the logical organ definition before multiple
engines can be supported cleanly.

The recommendation is to evolve the existing application, not rewrite
it.

## 3. Proposed multi-engine architecture

Separate three concerns:

1.  **Musical application and workflow:** notation, hymns, setlists,
    MIDI performance, recording, KeyLab controls and user interface.
2.  **Logical organ model:** divisions, stops, ranks, couplers,
    tremulants, expression, registrations and score events.
3.  **Engine adapters:** translate the logical organ model into the
    controls understood by each sound engine.

Potential engines: - GrandOrgue --- sampled virtual pipe organ. - Aeolus
--- additive-synthesis pipe-organ engine, with standalone and plugin
builds in the referenced project. - Other VST3/CLAP instruments or
MIDI-capable standalone applications, where their control interfaces
make integration practical.

A score or registration should describe musical intent through logical
stop and division names, rather than only storing a particular engine's
internal identifiers. Each adapter translates that intent into
engine-specific commands. Existing GrandOrgue-specific markers should
remain supported for backward compatibility.

## 4. Aeolus standalone as the first integration experiment

Repositories: - https://github.com/Archie3d/aeolus_plugin -
https://github.com/Archie3d/aeolus_plugin/releases

A key observation in the conversation is that a Windows standalone
executable exists and can receive MIDI. This offers a potentially
simpler first integration than embedding a plugin host inside
SimpleConsole.

Proposed signal path:

``` text
SimpleConsole
  - KeyLab and other MIDI controllers
  - Logical organ model
  - Registration and score events
  - Engine manager / Aeolus adapter
          |
          | Virtual MIDI connection
          v
Aeolus standalone executable
  - MIDI input
  - Organ synthesis
  - Independent audio processing
          |
          v
Windows audio device / recording route
```

SimpleConsole would launch and monitor Aeolus, connect to its MIDI
input, and translate logical note, stop, expression and registration
actions into Aeolus-compatible MIDI messages. Aeolus remains responsible
for synthesis and audio output.

A Windows virtual MIDI port (for example, one created with loopMIDI) is
a practical candidate for the proof of concept. Actual MIDI routing and
audio-device behaviour must be tested on the target system.

### Why this route is attractive

-   It avoids implementing a VST3/CLAP host as the first step.
-   Aeolus remains isolated in its own process.
-   Python does not need to process plugin audio buffers.
-   The adapter can focus on process management and MIDI translation.
-   It tests whether the logical organ model can control a second
    engine.

A standalone process is **not automatically more CPU-efficient** than a
plugin. Its advantage here is reduced integration complexity and process
isolation, not a guaranteed reduction in audio-processing overhead.

### Aeolus protocol: verify before implementation

The earlier discussion identified an Aeolus MIDI control scheme
involving CC98 stop-control messages, division/channel assignments,
Program Change registration steps and other controller messages. Verify
the exact protocol against the selected Aeolus version and authoritative
documentation before coding.

Confirm: - The precise CC98 message sequence and operation values. -
Division and control-channel assignments. - Whether stop states can be
queried or only commanded. - Program Change/registration-step
behaviour. - Expression and volume controller assignments. - MIDI input
selection and the Windows standalone build's behaviour.

Do not assume every build exposes identical controls or configuration
options.

## 5. Recommended development sequence

1.  Document which current organ-model fields are logical concepts and
    which are GrandOrgue-specific.
2.  Define an engine contract: start/stop, note input, stop activation,
    expression, registration recall, state reporting and error handling.
3.  Build an Aeolus standalone adapter, initially supporting process
    launch/exit and MIDI connection.
4.  Prove reliable note-on/note-off delivery from SimpleConsole to
    Aeolus.
5.  Prove stop switching, division control, expression and registration
    recall.
6.  Test whether Aeolus and GrandOrgue can coexist without unacceptable
    audio-device conflicts or latency.
7.  Connect score events to engine-neutral registrations while retaining
    existing GrandOrgue behaviour.
8.  Only then assess native plugin hosting.

The eventual engine manager should not care whether an engine is a
standalone executable, a plugin or an external MIDI device. It should
communicate through a defined adapter contract.

## 6. Plugin hosting as a later task

Direct VST3/CLAP hosting is feasible, but it is substantially larger
than launching a standalone MIDI instrument. A proper host must handle
plugin lifecycle, audio buffers, real-time thread safety, MIDI event
delivery, parameter discovery, plugin state, audio routing and
format-specific behaviour.

A native C++ audio subsystem (potentially using JUCE or a suitable CLAP
host implementation) could communicate with the existing Python/PySide6
application through a defined interface. There is no immediate reason to
rewrite the whole application in C++.

Plugin parameters are not necessarily organ stops. Names such as
"Brightness", "Drawbar 3" or "Parameter 1" cannot safely be interpreted
as "Principal 8′" or "Swell". A user-editable mapping/learn system and
saved per-engine mappings will be needed.

## 7. Honest assessment

### Technically credible

-   The existing controller and organ-layout work is a meaningful
    foundation.
-   Separating logical organ concepts from engine-specific controls is
    sound architecture.
-   Controlling a MIDI-capable Aeolus standalone process through virtual
    MIDI is a sensible first experiment.
-   Score-driven logical registrations could eventually operate across
    multiple engines.
-   A later plugin-hosting subsystem is possible without replacing the
    entire Python application.

### Not yet demonstrated

-   That the current codebase already has a complete engine-neutral
    organ model.
-   That the selected Aeolus Windows executable exposes every required
    stop and registration operation exactly as assumed.
-   That all MIDI control details cited in the earlier discussion match
    the selected release.
-   That GrandOrgue and Aeolus can share the intended audio
    configuration without practical conflicts.
-   That generic stop recognition can be automated reliably across
    arbitrary plugins.
-   That the complete hybrid workflow is already implemented.

### Principal risks

1.  **Model leakage:** GrandOrgue-specific identifiers may spread into
    supposedly generic score and registration data.
2.  **State synchronisation:** Sending a MIDI command does not prove
    that an engine accepted it or reached the requested state.
3.  **MIDI routing:** Port selection, channel assignments, duplicate
    messages and reliable note-off handling need care.
4.  **Audio configuration:** ASIO exclusivity, WASAPI modes, sample
    rates and device sharing can complicate simultaneous engines.
5.  **Scope expansion:** Plugin hosting and DAW-like features could
    distract from the original church-music workflow.

### Overall judgement

**The concept is feasible and worth pursuing incrementally.** The
strongest next move is not to build a universal plugin host. It is to
prove that SimpleConsole can control Aeolus standalone as a second,
independent organ engine. That tests the central architectural
assumption --- that the musical console can be separated from the
sound-producing engine --- at substantially lower engineering cost.

The project's differentiator is not simply that it can play more organ
sounds. It is the ambition to bring organ control, notation, liturgical
preparation, rehearsal, performance and recording together in an open,
approachable environment designed around the people who use it.

**The musician should not have to understand the machinery to use the
instrument.**

## 8. Relevant links

-   Main application:
    https://github.com/MackyBMC/GrandOrgue-Keylabs-Essential-SimpleConsole
-   Aeolus plugin and standalone project:
    https://github.com/Archie3d/aeolus_plugin
-   Aeolus releases: https://github.com/Archie3d/aeolus_plugin/releases
-   Arturia KeyLab Essential MIDI scripting reference:
    https://github.com/mchelmb/flstudio-arturia-keylab-essential

## 9. Closing perspective

The project began with a late-1980s ambition: make useful computer-based
music tools available to church musicians without forcing them into
fragmented workflows or proprietary dependencies. Current technology
makes a broader version of that idea possible. The discipline now is to
preserve the original purpose while making the architecture extensible.

Build the musical model first, prove the standalone engine bridge, and
add more complicated hosting technology only when justified by a real
user need.
