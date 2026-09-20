# KeyLab Essential 61 mk2 -> GrandOrgue (Friesach) Hardware Mapping

Reference doc for programming the Arturia MIDI Control Center (User Mode page)
and GrandOrgue's Audio/Midi Settings -> Initial MIDI tab ("Listen for event"
on each element). This is documentation only - it is not read by GrandOrgue
itself; GO's combination YAML has no MIDI-routing schema (see prior chat).

Everything below assumes a single consistent User Mode page, MIDI Channel 1,
all sent from one virtual port. DAW Mode is intentionally not used: it relies
on Mackie Control Universal / HUI handshake messages that only DAWs (Reaper,
Ableton, etc.) answer. GrandOrgue does not implement MCU/HUI, so DAW-mode
transport buttons and motorized faders stay inert against it - User Mode CC/
Note is the layer that actually works.

## Encoders (9)

| # | CC  | Function                                   | GO Initial MIDI group |
|---|-----|---------------------------------------------|------------------------|
| 1 | 74  | Pedal division volume                        | Manuals |
| 2 | 71  | Hauptwerk division volume                    | Manuals |
| 3 | 77  | Schwellwerk division volume                  | Manuals |
| 4 | 76  | Solowerk division volume                     | Manuals |
| 5 | 20  | Master (overall) volume                      | Master controls |
| 6 | 21  | Transpose (semitone)                         | Master controls |
| 7 | 22  | Fine tuning / concert pitch                  | Master controls |
| 8 | -   | Spare / reserved                             | - |
| 9 | -   | Spare / reserved                             | - |

## Faders (9)

| # | CC  | Function                                   | Notes |
|---|-----|---------------------------------------------|-------|
| 1 | 85  | Enclosure (Schwellwerk swell shade)          | Your primary real-time expression control |
| 2 | 23  | General Crescendo                            | GO's built-in 0-32 step crescendo shoe. It's *destructive* - overrides hand registration while active rather than layering on top of it |
| 3 | 24  | Coupler: Schwellwerk -> Hauptwerk ("I/II")   | Play on Hauptwerk, hear Schwellwerk's drawn stops too |
| 4 | 25  | Coupler: Solowerk -> Hauptwerk ("I/III")     | Play on Hauptwerk, hear Solowerk's drawn stops too |
| 5 | 26  | Coupler: Solowerk -> Schwellwerk ("II/III")  | Play on Schwellwerk, hear Solowerk's drawn stops too - this is the same "Coupler 6" already used in the Chorus Crescendo / Tutti / Grand Jeu Generals |
| 6 | 27  | Coupler: Hauptwerk -> Pedal                  | Reinforces the pedal line with Hauptwerk stops |
| 7 | 28  | Coupler: Schwellwerk -> Pedal                | Reinforces the pedal line with Schwellwerk stops |
| 8 | 29  | Coupler: Solowerk -> Pedal                   | Reinforces the pedal line with Solowerk stops |
| 9 | -   | Spare / reserved                             | No further couplers exist on this organ (6 total, all assigned above) |

Faders used as couplers act as a physical rocker rather than a smooth sweep -
GrandOrgue reads a "Listen for event" CC binding on a coupler/switch as a
threshold, not a continuous value: bottom half of the fader throw = off, top
half = on. Bind each one directly on the coupler itself (right-click the
coupler drawstop in GO's Hauptwerk/Schwellwerk/Pedal panel -> Properties ->
Listen for event), not through the combination YAML - same approach as the
Setter/Sequencer buttons.

Note: only these 6 intermanual/pedal couplers exist in the ODF - there's no
reverse-direction pair (e.g. no "Hauptwerk -> Schwellwerk"), so "I/II",
"I/III" and "II/III" above are one-directional exactly as built into this
organ, not a symmetrical pair of couplers per manual combination.

## Pads (8) - toggle mode

| Pad | Note | Function |
|-----|------|----------|
| 1   | 36   | General Cancel (all stops off) |
| 2   | 37   | Panic (MIDI/all-notes-off safety) |
| 3   | 38   | Set (store current registration into current sequencer slot) |
| 4   | 39   | **Tremulant 2 Man** (Schwellwerk tremolo) - live toggle |
| 5   | 40   | **Tremulant 3 Man** (Solowerk tremolo) - live toggle |
| 6   | 41   | Direct jump: General 001 - "001 - General Verse" |
| 7   | 42   | Direct jump: General 003 - "003 - Final Tutti Wall" |
| 8   | 43   | Direct jump: General 019 - "019 - Ave Verum Corpus - Récit doux" |

Swap pads 6-8 for whichever three of the 19 Generals you reach for most -
these are just a starting recommendation.

## Custom buttons (3) - Prev / Next / Live

| Button | CC | Function |
|--------|----|----------|
| Prev   | 17 | Sequencer Previous (step back through all 19 Generals) |
| Next   | 18 | Sequencer Next (step forward) |
| Live   | 19 | Direct jump to General 000 ("000 - Playover Intro" / home registration) |

## To wire this up

1. **Arturia MIDI Control Center**: set the encoders/faders/pads/buttons
   above on one User Mode page, all Channel 1, matching the CC/Note numbers
   in this table.
2. **GrandOrgue**: Audio/Midi Settings -> Initial MIDI tab (or right-click
   the element -> Properties -> Listen for event) for each target - play the
   corresponding hardware control and let GO learn it.
3. Save the organ's settings once done so the bindings persist across
   sessions.

## Open items to verify yourself

- Coupler naming/direction (Coupler 1-6) was inferred from the ODF's
  `DestinationManual` fields and coupler counts per manual, not from
  explicit labels - worth a quick listen test.
- Whether recalling a General truly resets stops *not* listed in it, or only
  changes what's listed. Both combination files were built listing every
  manual explicitly (including empty `stops: {}`) to guarantee a clean
  reset either way, but a real test in GO is worth doing before relying on
  it live.
