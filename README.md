# GrandOrgue KeyLab Essential Simple Console

A hardware control surface for [GrandOrgue](https://github.com/GrandOrgue/GrandOrgue)
using the Arturia KeyLab Essential 61 mk2 in DAW mode. The project connects the
KeyLab's buttons, jog wheel, faders, encoders, pads, LCD, and LEDs to a
GrandOrgue organ through a virtual MIDI cable.

The current configuration targets the Friesach organ and includes registration
combinations, MIDI settings, and hardware mappings for that setup.

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

Install the Python packages with `Scripts/install_requirements.bat`, or run:

```bat
python -m pip install --upgrade mido python-rtmidi pyyaml
```

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
