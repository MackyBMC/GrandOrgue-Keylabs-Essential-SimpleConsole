# KeyLab first-run tutorial

This guide covers the first launch of **KeyLab GrandOrgue Bridge** with an Arturia
KeyLab Essential 61 mk2 in DAW mode. Button behavior below follows the current
default configuration. The app's Config tab and `config.yaml` can change some
settings.

## Before the first launch

1. Connect the KeyLab and put it in **DAW** mode.
2. Install and open GrandOrgue, load the organ you want to use, and make sure its
   audio works.
3. Create the two virtual MIDI ports used by the Windows sample configuration:
   `GO2Bridge` and `Bridge2GO`.
4. In GrandOrgue's **Audio/MIDI > Settings > MIDI Devices**, enable the KeyLab
   **MAIN** input and the virtual cable input and output. Keep the KeyLab **DAW**
   port disabled in GrandOrgue; the bridge reads it.
5. Import the bridge MIDI assignments. To preserve existing GrandOrgue mappings,
   first export your current settings and merge the bridge assignments with
   `make_go_midi_import.py` as described in the main [README](../README.md#importing-midi-settings).

The default `config.yaml` uses the Friesach profile and Windows loopMIDI port
names. The installer can optionally copy starter combinations and MIDI settings
into the GrandOrgue user folder. If the configured organ file or MIDI devices are
not on your system, update the path and port-name fragments in the app's Config
tab before expecting the controls to reach the organ.

## What you see on first launch

The default interface is **Live / Main**. If GrandOrgue can be found, the app
attempts to launch it with the configured organ file. This does not configure
GrandOrgue's MIDI routes or install an organ; those are separate setup steps.

```text
┌───────────────────── Live / Main ───────────────────────────┐
│ Setter combinations │ Bank selector │ Transport / MIDI file │
│                     │ Pad/stop grid │ Volume controls       │
│                     │ Active stops  │                       │
└──────────────────────────────────────────────────────────────┘
```

- **Setter combinations** lists the available registration steps found in the
  configured `Combinations/Friesach` folder. The exact list depends on which
  starter files are present in your GrandOrgue data folder. The repository's
  Friesach starter set contains 31 files and 48 setter steps.
- **Bank selector and pads** show the currently selected stop bank. The eight
  faders and eight physical pads operate the same eight stops, couplers, or
  tremulants. The controller starts on the first bank, `P1` (Pedal).
- **Active stops** shows the stop state reported by GrandOrgue.
- **Transport** controls GrandOrgue's MIDI player and related bridge actions.
- **Volume controls** are also available in the GUI.

If the combination list is empty, check that `combination_set` is `Friesach` in
`config.yaml` and that the configured GrandOrgue folder contains the
`Combinations/Friesach` directory and its YAML files.

## The KeyLab controls at a glance

This is a functional map, not a scale drawing of the keyboard:

```text
  [<< Rewind] [>> Forward]        [Cat/Char] [◀ Left] [Right ▶] [Preset]

                    ┌────── jog wheel ──────┐
                    │ turn = browse / move  │
                    │ press = choose / load│
                    └───────────────────────┘

  [Part 2 / Prev bank]                       [Part 1 / Next bank]
  [Fader 1] [Fader 2] ... [Fader 8]                         [Master 9]
  [Encoder 1] [Encoder 2] ... [Encoder 8]
```

### Jog wheel and navigation

On **Live / Main**, turn the jog wheel to select the previous or next setter
combination. With the default `preset_activation: staged`, this only cues it; it
does not immediately change the organ. The LCD briefly shows the selected
combination and a cue message. Press the jog wheel to load it. The optional
**direct** preset mode activates a combination as soon as it is selected; if you
have unsaved stop changes, the app may ask whether to save, discard, or cancel.

The physical **<< Rewind** and **>> Forward** buttons move to the previous or
next step in the current setter sequence and activate that step. They are
different from turning the jog wheel, which browses the list of combinations.

### Tabs, Cat/Char, and jog press

The main tabs are ordered:

```text
Live / Main → Setter Editing → Combination Files → Couplings
      → System Console → Config → Organ Selection → (back to Live / Main)
```

- **Left / Right arrows** move between main tabs.
- **Cat/Char off:** the jog uses the current tab's main list or control. On Live /
  Main it browses setter combinations.
- **Cat/Char on:** the jog moves focus through the current tab's interactive
  controls. The Cat/Char light indicates this control-navigation mode.
- **Jog press** activates the focused item/control in control-navigation mode.
  On Live / Main with Cat/Char off, it loads the selected combination.
- Press **Cat/Char** again to return to normal jog behavior.

On **Combination Files**, a jog press opens the selected file for editing; it does
not load a setter onto the organ. Use the Live / Main combination list to load
setters.

### Preset, faders, pads, and banks

- **Preset** toggles the stop-grid mode for the pads. In normal mode, each pad
  toggles the stop in the current bank at that pad's position. In stop-grid mode,
  the jog and arrows move the grid focus and the pads operate the displayed slots.
- **Part 2 / Prev** selects the previous bank; **Part 1 / Next** selects the next.
  The LCD briefly shows the bank and fader-state marks.
- **Faders 1-8** control the corresponding item in the current bank when moved:
  at or above about halfway is ON; below halfway is OFF. An untouched fader does
  not change a stop just because you changed banks.
- **Fader 9 / Master** controls overall volume.
- Pad colors indicate state: bright means on, dim means off. The exact bank names
  and stops depend on the selected organ profile.

Default Friesach banks include pedal (`P1`, `P2`), Hauptwerk (`H1`, `H2`),
Schwellwerk (`S1`-`S3`), Solowerk (`L1`), and couplers (`C1`).

### Other buttons and encoders

| Control | Default action |
|---|---|
| Play/Pause | Play or pause the GrandOrgue MIDI player; if a recorded take is selected, play/pause that take instead |
| Stop | Stop playback and send Panic (all sound off) |
| Loop | Toggle repeat for GrandOrgue MIDI playback |
| Metro | Tap to toggle GrandOrgue's metronome; hold Metro and turn jog to raise/lower its tempo |
| Save | Send GrandOrgue's Save file command; GrandOrgue may open its own dialog |
| Record | Start/stop recording a MIDI take |
| Undo, Punch | No bridge action is assigned by default |
| Encoder 1 | Pedal volume |
| Encoder 2 | Hauptwerk volume |
| Encoder 3 | Solowerk volume |
| Encoder 4 | Schwellwerk volume |
| Encoder 5 | Schwellwerk swell/enclosure |
| Encoders 7 and 8 | Tremolo II / III: turn right for ON, left for OFF |
| Encoder 6 | Unassigned by default |

Volume encoders use relative steps; turning faster changes the value by more.
Encoder assignments can be changed in `config.yaml`.

## A gentle first-use sequence

1. Confirm GrandOrgue is open and the MIDI devices/routes are configured.
2. On Live / Main, turn the jog one click. Confirm the selected setter changes
   and the LCD briefly displays its cue message.
3. Press the jog wheel to load that setter. Confirm GrandOrgue's stops and the
   app's Active stops list update.
4. Move one fader slightly above halfway, then below halfway. Confirm that stop
   turns on and off. Select another bank with Part 1 / Part 2 and repeat.
5. Try the << / >> buttons to move within the loaded setter sequence.
6. Press Cat/Char, turn the jog to focus another control, and press the jog to
   activate it. Press Cat/Char again to exit that mode.
7. Use Stop only when you want to stop and silence playback; it sends Panic.

If a control does not work, first check the displayed port names and the
GrandOrgue MIDI import. From source, `python keylab_go_bridge.py --list` lists
ports. See the main README's [Troubleshooting section](../README.md#running-from-source-and-troubleshooting)
and the [hardware reference](../KeyLab_GrandOrgue_HardwareSettings.md) for more
detail.
