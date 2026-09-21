# KeyLab Essential 61 mk2 -> GrandOrgue (Friesach): control reference

Reference for `Scripts/keylab_go_bridge.py`, with the keyboard in **DAW mode** (press the DAW pad). This file is documentation only; the behaviour lives in the script and `Scripts/config.yaml`.

## Which port carries what

| Port | Carries | Read by |
| --- | --- | --- |
| KeyLab **MAIN** in | keys, pitch and mod wheels, sustain pedal (CC 64), pads (CCs), panel-button SysEx | GrandOrgue directly; the bridge also reads the pads |
| KeyLab **DAW** in | transport and navigation buttons, jog, encoders, faders (Mackie-style) | the bridge only - keep it **disabled** in GrandOrgue, or the button notes will play pipes |
| KeyLab out | LCD text and LED colours (SysEx) | written by the bridge |
| Virtual cable (LoopBe) | commands, stop states, volumes, label text | bridge <-> GrandOrgue |

## Buttons and wheels (DAW port unless noted)

| Control | Message | Action |
| --- | --- | --- |
| `<<` Rewind | note 0x5B | previous step in the loaded file (activates) |
| `>>` Forward | note 0x5C | next step in the loaded file (activates) |
| Jog turn | CC 0x3C, 0x01 right / 0x41 left | cue next / previous setter file (does not activate) |
| Jog press | note 0x54 | load the cued file (same as the sustain pedal) |
| Sustain pedal | CC 64, MAIN port | GrandOrgue **Load file** (direct, not through the bridge) |
| Part 1 / Next | note 0x31 (0x2F in bank mode) | next fader/pad bank |
| Part 2 / Prev | note 0x30 (0x2E in bank mode) | previous fader/pad bank |
| Save | note 0x50 | GrandOrgue **Save file** (opens its own dialog) |
| Metro | note 0x59 | GrandOrgue metronome on/off |
| Play/Pause | note 0x5E | GrandOrgue MIDI player play / pause (load the file in GrandOrgue first) |
| Stop | note 0x5D | **Panic**; if the MIDI player is playing or paused it is stopped first |
| Loop | note 0x56 | repeat the MIDI file (the bridge restarts Play when it ends) |
| Undo, Punch, Record, Cat/Char, Preset, arrows | 0x51, 0x57/0x58, 0x5F, 0x65, 0x64, 0x62/0x63 | not assigned |
| Live / Bank | (nothing) | switches Part 1/2 between channel notes (0x30/0x31) and bank notes (0x2E/0x2F); both work |

## Faders, encoders and volumes

| Control | Message | Action |
| --- | --- | --- |
| Faders 1-8 | pitch bend, channels 1-8 | a fader you move sets its stop on (at or above half travel) or off; untouched faders change nothing |
| Fader 9 (master) | pitch bend, channel 9 | master volume |
| Encoders 1-4 | CC 0x10-0x13, relative | Pedal, Hauptwerk, Solowerk, Schwellwerk volume |
| Encoders 7, 8 | CC 0x16, 0x17, relative | Tremolo II, Tremolo III: turn right = on, left = off |
| Encoders 5, 6 | CC 0x14, 0x15 | not assigned |
| Encoder 9 | (sends nothing in DAW mode) | - |

Encoder values are relative: `0x01` = one click right, `0x41` = one click left, larger values when turned fast.

## Fader and pad banks

Fader *n* and pad *n* control the same item in the current bank; Part 1/2 change the bank for both. Banks are cut from each division's stops in the organ's own order, eight at a time. The CC number (channel 15) is fixed and never depends on the bank.

| Bank | Division | Pad colour | Faders / pads 1-8 (CC) |
| ---- | -------- | ---------- | ---------------------- |
| P1 | Pedal | blue | 1 Untersatz 32' (1); 2 Contrabass 16' (2); 3 Subbass 16' (3); 4 Octavbass 8' (4); 5 Gedackt 8' (5); 6 Choralbass 4' (6); 7 Posaune 32' (7); 8 Posaune 16' (8) |
| P2 | Pedal | blue | 1 Trompete 8' (9) |
| H1 | Hauptwerk | green | 1 Praestant 16' (10); 2 Principal 8' (11); 3 Holzflote 8' (12); 4 Rohrflote 8' (13); 5 Gambe 8' (14); 6 Octave 4' (15); 7 Spitzflote 4' (16); 8 Quinte 2 2/3' (17) |
| H2 | Hauptwerk | green | 1 Octave 2' (18); 2 Mixtur mj 2 2/3' (19); 3 Mixtur mi 1 1/3' (20); 4 Trompete 16' (21); 5 Trompete 8' (22) |
| S1 | Schwellwerk | yellow | 1 Bourdon 16' (23); 2 Principal 8' (24); 3 Nacht.Ged. 8' (25); 4 Corno dolce 8' (26); 5 Viola 8' (27); 6 V. celeste 8' (28); 7 Geigenpr. 4' (29); 8 Querflote 4' (30) |
| S2 | Schwellwerk | yellow | 1 Nazard 2 2/3' (31); 2 Flageolett 2' (32); 3 Tierce 1 3/5' (33); 4 Larigot 1 1/3' (34); 5 Plein jeu 2' (35); 6 Scharff 1' (36); 7 Trp. harm. 8' (37); 8 Hautbois 8' (38) |
| S3 | Schwellwerk | yellow | 1 Clairon 4' (39); 2 Tremolo II (51) |
| L1 | Solowerk | red | 1 Jubalflote 8' (40); 2 Trichterfl. 4' (41); 3 Cornet 8' (42); 4 Trp.chamade 8' (43); 5 Engl. Horn 8' (44); 6 Tremolo III (52) |
| C1 | Couplers | purple | 1 Coupler 1 (ped) (45); 2 Coupler 2 (ped) (46); 3 Coupler 3 (ped) (47); 4 Coupler 4 (HW) (48); 5 Coupler 5 (HW) (49); 6 Coupler 6 (SW) (50) |

Pad LEDs: full colour = stop on, dim = stop off (`pads: dim` in `config.yaml`). Tremolo II sits in the Schwellwerk bank and Tremolo III in the Solowerk bank (`layout: tremolos`).

## Pads on the MAIN port

In DAW mode the pads send CCs, not notes, and this keyboard's numbering is irregular (measured on firmware 1.1.10):

| Pad | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CC | 36 | 38 | 39 | 40 | 40 | 41 | 42 | 43 |

Pad 4 is a toggle (a lone *down* on one press, a lone *up* on the next) and pad 5 is momentary (down then up), both on CC 40. The bridge tells them apart by whether a release follows within `pads: shared_window` seconds. Very long presses of pad 5 are misread as pad 4. Run `--learn-pads` if your unit differs.

## LCD (16 x 2)

Normal display: the top-left two characters are the bank (for example `H2`), the bottom-left two are the step number in the loaded file, or `->` when a file is cued and waiting for Load. The rest shows the current file name.

Moving a fader, encoder or pad shows a readout (stop name and state, or a volume bar) that returns to the normal display after `display: hold` seconds. The keyboard draws its own text on fader moves; the bridge writes over it every `display: live` seconds. The normal display is also re-sent every `display: refresh` seconds.

## MIDI vocabulary used with GrandOrgue

Defined in `Settings/Friesach-midi-settings-KeyLab.yaml` and in the constants at the top of the bridge; do not change one without the other.

| Channel | Direction | Use |
| --- | --- | --- |
| 16 | bridge -> GrandOrgue | commands: CC 1 previous step, 2 next step, 3 previous file, 4 next file, 5 load file, 6 save file, 7 metronome, 8 play, 9 stop, 10 pause, 11 panic (127 then 0) |
| 15 | both ways | stops, couplers and tremolos: CC 1-52, 127 = on, 0 = off; GrandOrgue reports state changes back |
| 14 | GrandOrgue -> bridge | button state: CC 1 Load file lit (a file is cued), 2 Play lit, 3 Pause lit, 4 metronome on |
| 12 | bridge -> GrandOrgue | volumes: CC 1 master, 2 Pedal, 3 Hauptwerk, 4 Schwellwerk, 5 Solowerk, 6 Noises |
| - | GrandOrgue -> bridge | label text as Hauptwerk SysEx: file name (LCD, key 1) and step number (string, key 2) |

In Friesach the panel knobs are GrandOrgue *Switch* objects, not Stop objects, so the stop assignments target `manuals/<n>/switches/<m>` (stops follow the couplers in each manual's list: Pedal +3, Hauptwerk +2, Schwellwerk +1, Solowerk +0). The two tremolo buttons are the global switches `047` and `053`. The tremulant objects behind them are read-only in GrandOrgue (their state is computed from switches by the organ definition), so MIDI cannot set them directly.

## Importing into GrandOrgue

GrandOrgue's MIDI Objects **Import** clears every object that is *not* in the file. Export your own settings first, then run

```bat
python make_go_midi_import.py your-export.yaml merged.yaml
```

and import `merged.yaml`, which keeps your existing assignments and adds the bridge's. Check the GrandOrgue log afterwards: an "Unused MIDI object path" warning names a path that does not exist in your organ.

## Known limits

- GrandOrgue can only *play* a MIDI file that is already loaded; loading is done from its own menu.
- An accidental pedal press always reloads the file and returns to step 0, because that is what Load file does.
- The keyboard's pad colours drift, so the bridge re-sends them regularly (`pads: refresh`).
- Combination file names with accented letters may not display correctly on the LCD; ASCII names are safest.
