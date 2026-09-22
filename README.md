# GrandOrgue KeyLab Essential Simple Console

A hardware control surface for [GrandOrgue](https://github.com/GrandOrgue/GrandOrgue)
using the Arturia KeyLab Essential 61 mk2 in DAW mode. The project connects the
KeyLab's buttons, jog wheel, faders, encoders, pads, LCD, and LEDs to a
GrandOrgue organ through a virtual MIDI cable.

The current configuration targets the Friesach organ and includes registration
combinations, MIDI settings, and hardware mappings for that setup.

# Practical Purpose and use case for this Tool

This tool lets you use an Arturia KeyLab Essential 61/Mk2 as a simple,
practical MIDI organ console for GrandOrgue, with live performance in mind
and useful controls right under your hands. It’s aimed at players who want an accessible, 
affordable setup for enjoying and exploring virtual organs, 
while recognizing that dedicated organists may naturally want the depth and feel of a full traditional console.

The tool provides a custom GrandOrgue instrument configuration for the KeyLab, 
with the controls already mapped and a set of carefully selected, practical defaults. 
In other words, you can load it and start playing without having to build the MIDI mappings yourself.

## Base Organ: Friesach

This project uses the **Friesach Parish Church** sample set by Piotr Grabowski
as its base organ. The full sample set is free and supports GrandOrgue. Get it
from the official source:

- [Friesach Parish Church sample set - Piotr Grabowski](https://piotrgrabowski.pl/friesach/)
- [GrandOrgue download page](https://grandorgue.com/download/)

On the Friesach page, choose **Full free version** and complete the free
checkout to receive the download link. The full 24-bit version needs about
13 GB of free RAM for all release samples; the 16-bit version needs about
6.6 GB. The sample files are not included in this repository.

## What It Does

- Navigates and loads GrandOrgue sequencer and setter files.
- Moves through registration steps and cues the previous or next file.
- Uses eight faders as banked stop, coupler, and tremulant controls.
- Controls master and division volume with the master fader and encoders.
- Controls MIDI playback, looping, stopping, panic, saving, and the metronome.
- Shows the active file, step, stop state, and volume feedback on the KeyLab LCD.
- Shows playback state and bank/stop state with KeyLab LEDs and pad colors.
- Reads pad controls from the KeyLab MAIN port, including the shared pad 4/5
  behavior found on this keyboard.
- Keeps normal keyboard, pedal, and wheel input connected directly to GrandOrgue;
  playing does not pass through Python.

## How It Works

```text
KeyLab DAW port  ->  keylab_go_bridge.py  ->  virtual MIDI cable  ->  GrandOrgue
KeyLab LCD/LEDs  <-  keylab_go_bridge.py  <-  GrandOrgue feedback
KeyLab MAIN port ----------------------------------------------> GrandOrgue
```

The bridge sends command messages on MIDI channel 16, stop and switch messages
on channel 15, feedback is read on channel 14, and volume messages are sent on
channel 12. The generated GrandOrgue MIDI settings file describes these routes.

## Requirements

- Windows with GrandOrgue installed.
- Arturia KeyLab Essential 61 mk2.
- A virtual MIDI cable such as LoopBe or loopMIDI.
- Python 3.
- Python packages: `mido`, `python-rtmidi`, and `pyyaml`.

## GrandOrgue Knowledge and Installation

This project assumes that the user already knows how to install GrandOrgue,
load an organ and its sample set, select audio and MIDI devices, and change
GrandOrgue settings. The bridge is an integration layer for an existing
GrandOrgue installation; it is not a replacement for GrandOrgue's setup or
organ-loading workflow.

Install GrandOrgue from the official resources:

- [Official GrandOrgue download page](https://grandorgue.com/download/)
- [GrandOrgue project on GitHub](https://github.com/GrandOrgue/grandorgue)
- [GrandOrgue community discussions](https://github.com/GrandOrgue/grandorgue/discussions)

After installing GrandOrgue, obtain and load the Friesach organ and its sample
set before applying this project's MIDI settings. See [Base Organ: Friesach](#base-organ-friesach)
for the official free sample-set source.

Install the Python packages with `Scripts/install_requirements.bat`, or run:

```bat
python -m pip install --upgrade mido python-rtmidi pyyaml
```

## Tested With

- GrandOrgue v3.17.3-1
- Arturia KeyLab Essential 61 mk2, firmware 1.1.10, in DAW mode
- Windows 11, Python 3.13
- LoopBe1 as the virtual MIDI cable

This has been tried on one setup only. Pad numbering and some DAW-mode behaviour
can differ between keyboards and firmware versions (see the control reference).

## GrandOrgue Setup

In GrandOrgue open **Audio/MIDI > Settings > MIDI Devices** and enable:

- the KeyLab **MAIN** input (keys, pitch and mod wheels, sustain pedal),
- the virtual cable as both an **input** and an **output**.

Leave the KeyLab **DAW** input **disabled** in GrandOrgue. Its button messages are
ordinary notes and would sound pipes. Only the bridge reads that port.

Put the keyboard in DAW mode by pressing the **DAW** pad.

The bridge does not open the KeyLab MAIN port by default because Windows MIDI/WinMM
may not allow GrandOrgue and the bridge to open that input at the same time. The
default configuration therefore leaves MAIN with GrandOrgue, so keys, wheels and
sustain continue to work. Pad presses require a MIDI splitter or MIDI service that
supports shared input; the pad lights can still be driven by the bridge.

## Quick Start

1. Connect the KeyLab and start GrandOrgue.
2. Create or select the virtual MIDI cable used by both applications.
3. Import `Settings/Friesach-midi-settings-KeyLab.yaml` into GrandOrgue.
4. Update `Scripts/config.yaml` with the MIDI port names on the local machine.
5. Run `Scripts/start_keylab_bridge.bat`.

To inspect available MIDI ports without starting the bridge:

```bat
python Scripts/keylab_go_bridge.py --list
```

The batch file uses `Scripts/config.yaml` by default. Command-line options can
override its values, for example:

```bat
python Scripts/keylab_go_bridge.py --go "LoopBe" --kl-in "DAW" --kl-out "KeyLab" --kl-main "Ess Midi In"
```

Use `--verbose` for MIDI diagnostics. Use `--learn-pads` to identify the pad
CC numbers and update `config.yaml`.

## Importing the MIDI Settings

GrandOrgue's MIDI Objects **Import** clears every object that is *not* in the file
you import, and `Settings/Friesach-midi-settings-KeyLab.yaml` contains the author's
own device names. Before importing:

1. In GrandOrgue open the MIDI Objects dialog and **Export** your current settings.
2. Merge the bridge's assignments into your export:

   ```bat
   python Scripts/make_go_midi_import.py your-export.yaml merged.yaml
   ```

3. **Import** `merged.yaml`.
4. Open the GrandOrgue log. An "Unused MIDI object path" warning names an object that
   does not exist in your organ.

The assignments target the Friesach sample set. Its panel knobs are GrandOrgue
*Switch* objects, so the paths are of the form `manuals/<n>/switches/<m>`. Another
organ needs its own stop names and switch numbers in `Scripts/keylab_go_bridge.py`.

## Troubleshooting

- `--list` prints the exact MIDI port names on the machine.
- `--verbose` prints every message the bridge sends and receives.
- `--test-stop 11 --test-off` switches one stop off without touching a fader
  (11 is the Hauptwerk Principal 8'). Run it again without `--test-off` to switch it back on.
- LCD stays blank: try the other KeyLab output port with `--kl-out`.
- Pad presses do nothing: check `--learn-pads`, then the pad CC list in `config.yaml`.
- `keylab_sniffer.py` shows the raw messages of every KeyLab port, labelled MAIN or DAW.

## Repository Layout

- `Scripts/`: main MIDI bridge, diagnostics, LED test, and import helper.
- `Settings/`: GrandOrgue MIDI settings exports.
- `Combinations/`: Friesach registration combinations.
- `workings/`: experimental and supporting combinations, bridge variants, and
  working notes.
- `KeyLab_GrandOrgue_HardwareSettings.md`: physical control mapping reference.

`Scripts/make_go_midi_import.py` merges the bridge assignments into a
GrandOrgue MIDI settings export while preserving existing assignments:

```bat
python Scripts/make_go_midi_import.py input.yaml output.yaml
```

The LCD-only helpers in `workings/` can be used when the full bridge is not
needed. `keylab_sniffer.py` scripts record or print raw KeyLab messages for
diagnosing port and control mappings.

## Repository Scope

The repository contains source code, documentation, text configuration, MIDI
settings, and registration definitions. Actual GrandOrgue organ packages,
audio samples and recordings, MIDI recordings, cache files, combination
database files, and ZIP archives are intentionally excluded by `.gitignore`.

## Future Organ Support

Friesach is the base organ for the current implementation. Additional organs
will be added over time as the control mappings are generalized and the current
integration's kinks and organ-specific issues are worked out. Each organ may
require its own stop names, switch paths, MIDI settings, and tested control
mapping before it can be supported reliably.

## Known Limits

- GrandOrgue can only *play* a MIDI file that is already loaded; loading is done from
  its own menu, not by MIDI.
- Load file always reloads the file and returns to step 0, so an accidental sustain
  pedal press resets the registration.
- The keyboard's pad colours drift, so the bridge re-sends them regularly.
- In DAW mode pad 4 and pad 5 send the same CC; the bridge separates them by their
  press pattern. Very long presses of pad 5 can be read as pad 4.
- Accented letters in combination file names may not display correctly on the LCD.
- The Friesach organ definition wires its tremulants unusually: Tremolo II is not
  connected to its own tremulant, and Tremolo III only works while the Blower switch
  is on. See the control reference for details.

## How This Was Made

The bridge, the GrandOrgue MIDI settings generator, the diagnostic and test scripts,
the control reference and the registration files added for this project were written
**almost entirely by Claude Sonnet 5**, an AI model made by Anthropic, in a long
working conversation with the project's author.

The author (MackyBMC) supplied the organ, the keyboard and the ideas, made the design
decisions, and ran every test on real hardware. Each capture, log and screenshot from
those tests went back to Claude, which corrected and extended the code from it. Claude
also read the source of GrandOrgue and of rjuang's script to work out the MIDI message
formats and object paths.

Because the code is AI-generated and has been tried on one setup, review it before
relying on it, especially for live performance.

## Acknowledgements

- **Claude Sonnet 5** (Anthropic) - wrote nearly all of the code in this repository, as
  described above.
- **rjuang** - [flstudio-arturia-keylab-mk2](https://github.com/rjuang/flstudio-arturia-keylab-mk2)
  (MIT) documents how the KeyLab display and LEDs are driven; the LCD frame and LED
  numbers used here come from studying it.
- **Piotr Grabowski** - the Friesach Parish Church sample set this project is built on.
- **The GrandOrgue project** - its source was consulted to learn the MIDI object paths
  and event formats. No GrandOrgue code is included here.

## License

MIT. See [LICENSE](LICENSE).

## Disclaimer

This project is not affiliated with or endorsed by Arturia, GrandOrgue, Piotr Grabowski
or Anthropic. KeyLab and Arturia are trademarks of Arturia SA; Claude is a trademark of
Anthropic. Use at your own risk.
