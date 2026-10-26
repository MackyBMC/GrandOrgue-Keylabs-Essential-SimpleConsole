# GrandOrgue KeyLab Essential Simple Console

A hardware control surface for [GrandOrgue](https://github.com/GrandOrgue/GrandOrgue)
using the Arturia KeyLab Essential 61 mk2 in DAW mode. The project connects the
KeyLab's buttons, jog wheel, faders, encoders, pads, LCD, and LEDs to a
GrandOrgue organ through a virtual MIDI cable.

Friesach is the initial fully mapped organ profile and reference implementation.
The console architecture is intended to grow to additional organs, each with its
own tested stop map, MIDI settings, organ file, and registration resources.

## Practical Purpose and use case for this Tool

This tool lets you use an Arturia KeyLab Essential 61/Mk2 as a simple,
practical MIDI organ console for GrandOrgue, with live performance in mind
and useful controls right under your hands. It’s aimed at players who want an accessible, 
affordable setup for enjoying and exploring virtual organs, 
while recognizing that dedicated organists may naturally want the depth and feel of a full traditional console.

The tool provides a custom GrandOrgue instrument configuration for the KeyLab, 
with the controls already mapped and a set of carefully selected, practical defaults. 
In other words, you can load it and start playing without having to build the MIDI mappings yourself.

## What's new in 2.0

Version 2.0 turns the bridge into a small application. See [CHANGELOG.md](CHANGELOG.md) for the full list.

- **Windows application and installer.** A compiled `KeyLabGrandOrgueBridge.exe` with a proper installer: *Standard* (program files separate, settings in `%APPDATA%\KeyLabGrandOrgue`) or *Portable* (everything in one folder you choose). No Python needed for end users.
- **Your own GrandOrgue folder.** The installer asks where your GrandOrgue user folder is (Organs, Settings, Combinations) and checks for GrandOrgue and loopMIDI, with download links.
- **Qt GUI** with global themes, icon packs, and remembered window positions and sizes.
- **Stave Station:** a MIDI-to-score editor with engraved staves (Verovio), a piano-roll window, voices, rest tidying, fingerings, division and coupler labels, tonic sol-fa, lyrics, title/composer/arranger credits, pedal staff and track selection. Your original MIDI takes stay untouched; the stave shows a quantised version.
- **Take recorder and player** with a realtime-priority playback thread.
- **Releases built by GitHub Actions** on a `v*` tag, with `SHA256SUMS`. Linux and macOS packaging is included as an *experimental* framework.
- **Separate development folder.** Source lives in its own repository folder, no longer inside the GrandOrgue user folder.

The v1.0 releases remain available on the [Releases page](../../releases) and their tags are unchanged.

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
- Supports KeyLab pad controls when a MIDI splitter or shared-input MIDI service
  is available; by default, the MAIN port remains owned by GrandOrgue.
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

- Windows 10/11 with [GrandOrgue](https://grandorgue.com/download/) installed.
- Arturia KeyLab Essential 61 mk2.
- A virtual MIDI cable such as [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html) (ports `GO2Bridge` and `Bridge2GO`).
- Installed release: nothing else. Running from source: Python 3.11+ and `pip install -r requirements.txt`.

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

After installing GrandOrgue, obtain and load the organ profile you want to use
before applying its MIDI settings. For the initial supported profile, obtain the
Friesach organ and sample set described in [Base Organ: Friesach](#base-organ-friesach).

## Tested With

- GrandOrgue v3.17.3-1
- Arturia KeyLab Essential 61 mk2, firmware 1.1.10, in DAW mode
- Windows 11, Python 3.13
- loopMIDI with `GO2Bridge` and `Bridge2GO` ports

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

## Installing 2.0

Download `KeyLabGrandOrgueBridge-2.0.0-setup.exe` from the [latest release](../../releases/latest) and check it against `SHA256SUMS.txt`. The wizard asks:

1. **Installation type:** *Standard* installs the program normally and keeps settings and takes in `%APPDATA%\KeyLabGrandOrgue`. *Portable* keeps program and settings together in the folder you pick (an empty `portable.flag` file is placed beside the exe).
2. **GrandOrgue folder:** where your Organs / Settings / Combinations live. The default is `Documents\GrandOrgue`; choose another if you moved it. The choice is saved in `go_folder.txt`.
3. **Optional:** copy the starter Combinations and MIDI settings into that folder (existing files are never overwritten).

Uninstalling removes the program only; your settings, takes and GrandOrgue folder are kept. Unsigned executables may trigger Windows SmartScreen or antivirus warnings; the release publishes checksums so you can verify the download.

Version 2.0 installs next to v1.0 (different installer ID) and does not overwrite it.

## Quick Start

1. Connect the KeyLab and start GrandOrgue; create the loopMIDI ports `GO2Bridge` and `Bridge2GO`.
2. Import `Settings/Friesach-midi-settings-KeyLab.yaml` into GrandOrgue (see *Importing the MIDI Settings* below).
3. Start **KeyLab GrandOrgue Bridge** from the Start menu and select your MIDI ports in the settings.
4. Press the **DAW** pad on the keyboard.

From source: `python keylab_go_bridge.py` (add `--list` to print the exact MIDI port names, `--verbose` for diagnostics, `--learn-pads` to identify pad CC numbers). Command-line options override `config.yaml`.

## Configuration Options

`config.yaml` is the permanent Friesach setup. The main exposed options are:

- `organ_path`: GrandOrgue organ file the bridge works with. The default
  is the Full Image Resolution Friesach organ.
- `ports.go` and `ports.go_out`: the two virtual MIDI ports. With loopMIDI these
  are `GO2Bridge` and `Bridge2GO`.
- `ports.keylab_in`, `ports.keylab_out`, and `ports.keylab_main_in`: KeyLab DAW,
  output, and MAIN port name fragments.
- `ports.relay_main_out` and `ports.relay_main_in`: optional fallback relay when
  GrandOrgue and the bridge cannot share the physical MAIN input. GrandOrgue must
  be configured to read the relay output in that mode.
- `faders.threshold`: the fader value at which a stop switches on.
- `display.hold`, `display.live`, and `display.refresh`: LCD timing controls.
- `pads.enabled`, `pads.ccs`, `pads.shared_window`, `pads.refresh`, `pads.dim`,
  and `pads.colors`: pad behavior and LED colors.
- `controls.encoder_step`, `controls.volume_start`, `controls.jog_max_steps`,
  `controls.loop_restart`, and `controls.encoders`: encoder and transport behavior.
- `verbose`: enables recent MIDI messages in the fixed TUI dashboard.

## Importing the MIDI Settings

GrandOrgue's MIDI Objects **Import** clears every object that is *not* in the file
you import, and `Settings/Friesach-midi-settings-KeyLab.yaml` contains the author's
own device names. Before importing:

1. In GrandOrgue open the MIDI Objects dialog and **Export** your current settings.
2. Merge the bridge's assignments into your export:

   ```bat
   python make_go_midi_import.py your-export.yaml merged.yaml
   ```

3. **Import** `merged.yaml`.
4. Open the GrandOrgue log. An "Unused MIDI object path" warning names an object that
   does not exist in your organ.

The assignments target the Friesach sample set. Its panel knobs are GrandOrgue
*Switch* objects, so the paths are of the form `manuals/<n>/switches/<m>`. Another
organ needs its own stop names and switch numbers in `keylab_go_bridge.py`.

## Troubleshooting

- `--list` prints the exact MIDI port names on the machine.
- `--verbose` prints every message the bridge sends and receives.
- `--test-stop 11 --test-off` switches one stop off without touching a fader
  (11 is the Hauptwerk Principal 8'). Run it again without `--test-off` to switch it back on.
- LCD stays blank: try the other KeyLab output port with `--kl-out`.
- Pad presses do nothing: the MAIN input is normally reserved for GrandOrgue;
  use a MIDI splitter/shared-input service before selecting it in the setup console.

## Building and Releasing (developers)

```powershell
git clone https://github.com/MackyBMC/GrandOrgue-Keylabs-Essential-SimpleConsole
cd GrandOrgue-Keylabs-Essential-SimpleConsole
pip install -r requirements.txt
python keylab_go_bridge.py                                  # run from source (settings stay in the repo folder)
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1                  # Nuitka build + Inno Setup installer
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1 -InstallerOnly   # reuse the last build
```

Requires Inno Setup 6 (`winget install JRSoftware.InnoSetup`). The release steps are in [docs/RELEASING.md](docs/RELEASING.md): bump `version.py` and the installer version, update the changelog, tag `vX.Y.Z`, and GitHub Actions builds and publishes. `packaging/build_all.sh` is an experimental Linux (AppImage) / macOS (dmg) pathway that has not been tested on real machines.

`tools/tidy_scripts_folder.py` lists (dry run) and archives files in an old scripts folder that the app does not need. `tools/setup_dev_repo.ps1` builds a clean development repository from one.

## Repository Layout

- `keylab_go_bridge.py`, `keylab_bridge/`: the bridge engine (MIDI, LCD/LEDs, take recorder, paths).
- `qt_gui.py`, `themes*.py`, `polish.py`: the Qt interface and theming.
- `midi_stave/`: Stave Station (scoring, engraving, piano roll).
- `make_go_midi_import.py`: merges the bridge assignments into a GrandOrgue MIDI settings export.
- `Settings/`, `Combinations/`, `workings/`: GrandOrgue MIDI settings, Friesach registration combinations, working notes.
- `packaging/`: Nuitka build, Inno Setup installer, Linux/macOS framework, `v1_installer_reference.iss`.
- `.github/`: release workflow and sponsor links.
- `docs/`, `tools/`: release notes and maintenance tools.
- `KeyLab_GrandOrgue_HardwareSettings.md`: physical control mapping reference.

## Repository Scope

The repository contains source code, documentation, text configuration, MIDI
settings, and registration definitions. Actual GrandOrgue organ packages,
audio samples and recordings, MIDI recordings, cache files, combination
database files, and ZIP archives are intentionally excluded by `.gitignore`.

## Organ Profiles and Future Support

Friesach is the initial well-mapped organ profile and the current release's
reference implementation. The shared KeyLab bridge, TUI diagnostics, launchers,
and installer are intended to support additional organ profiles over time.

Each new organ will need its own tested stop and switch paths, MIDI settings,
organ file selection, combinations, and any organ-specific control behavior.
Until a profile is documented and tested, the existing Friesach mappings should
not be assumed to work for it.

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
- Linux and macOS packages are an untested framework; Windows is the supported platform.
- Executables are unsigned, so Windows SmartScreen may warn on first run.

## Support the Project

If this tool is useful, you can support its development via the **Sponsor** button on the repository page (GitHub Sponsors / Ko-fi). It is entirely optional; the software stays free.

## How This Was Made

The bridge, the GrandOrgue MIDI settings generator, the diagnostic and test scripts,
the control reference and the registration files added for this project were written
**almost entirely by Claude**, an AI model made by Anthropic, in a long
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
- **Third-party libraries** (PySide6, Verovio, music21, mido, python-rtmidi and others): see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## License

MIT. See [LICENSE](LICENSE).

## Disclaimer

This project is not affiliated with or endorsed by Arturia, GrandOrgue, Piotr Grabowski
or Anthropic. KeyLab and Arturia are trademarks of Arturia SA; Claude is a trademark of
Anthropic. Use at your own risk.
