# GrandOrgue KeyLab Essential Simple Console

A practical MIDI control surface for [GrandOrgue](https://github.com/GrandOrgue/grandorgue),
using an Arturia KeyLab Essential 61 mk2 in DAW mode. The bridge connects the KeyLab's
buttons, jog wheel, faders, encoders, pads, LCD, and LEDs to a GrandOrgue organ through
MIDI.

The aim is to make a capable virtual organ setup more accessible: give players useful
controls close at hand, provide a ready-to-use Friesach organ profile, and let people
play and explore without first having to build every MIDI mapping themselves. This is
an integration aid, not a replacement for GrandOrgue or a full traditional organ
console. The project is designed to grow to other organs as their mappings and
registration resources are tested.

## Releases and platform status

| Platform | Release | Status |
|---|---|---|
| Windows | [v2.0.3 stable release](https://github.com/MackyBMC/GrandOrgue-Keylabs-Essential-SimpleConsole/releases/tag/v2.0.3) | Supported; tested on the maintainer's Windows 11 setup |
| Linux | [v2.0.3 experimental package](https://github.com/MackyBMC/GrandOrgue-Keylabs-Essential-SimpleConsole/releases/tag/v2.0.3) | Build is available for evaluation; MIDI routing and hardware have not been validated on a real Linux system |
| macOS | None yet | Deferred until a later release and testing |

The Linux archive is experimental and is included alongside the stable Windows
release. Linux users will need to configure MIDI ports for their own system; the
Windows `loopMIDI` port names and sample configuration are not Linux defaults. See
[Known limits](#known-limits) before trying the experimental build.

## What the bridge does

- Navigates GrandOrgue sequencer and setter files, moves through registration steps,
  and cues the previous or next file.
- Uses eight faders as banked stop, coupler, and tremulant controls.
- Controls master and division volume with the master fader and encoders.
- Controls MIDI playback, looping, stopping, panic, saving, and the metronome.
- Shows the active file, step, stop state, and volume feedback on the KeyLab LCD.
- Displays playback state and bank/stop state with KeyLab LEDs and pad colors.
- Supports pad controls when the MIDI input can be shared or split. By default,
  GrandOrgue retains the KeyLab MAIN input.
- Keeps normal keyboard, pedal, and wheel input connected directly to GrandOrgue;
  playing does not pass through the Python bridge.
- Includes **Stave Station**, a MIDI-to-score editor with piano roll, voices, rest
  tidying, fingerings, division and coupler labels, tonic sol-fa, lyrics, track
  selection, and score engraving.
- Includes take recording and playback, a Qt GUI, themes, icon packs, and remembered
  window positions.

## How it works

```text
KeyLab DAW port  ->  KeyLab GrandOrgue Bridge  ->  virtual MIDI connection  ->  GrandOrgue
KeyLab LCD/LEDs  <-  KeyLab GrandOrgue Bridge  <-  GrandOrgue feedback
KeyLab MAIN port ----------------------------------------------------------->  GrandOrgue
```

The bridge sends command messages on MIDI channel 16, stop and switch messages on
channel 15, reads feedback on channel 14, and sends volume messages on channel 12.
The generated GrandOrgue MIDI settings file describes these routes.

## Requirements

### Windows stable release

- Windows 10 or 11.
- [GrandOrgue](https://grandorgue.com/download/) and the organ/sample set you want
  to use.
- An Arturia KeyLab Essential 61 mk2.
- A virtual MIDI cable such as
  [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html), with ports
  `GO2Bridge` and `Bridge2GO`.

The installed release does not require a separate Python installation.

### Linux experimental prerelease

The project builds on Linux, and GrandOrgue supports Linux, but this bridge's MIDI
routing and KeyLab hardware path have not yet been tested end-to-end on a Linux
desktop. The RtMidi backend supports ALSA and JACK on Linux; a virtual MIDI
connection must be available through the backend and configured for the machine.
PipeWire setups vary, so compatibility and routing need to be verified on the
target desktop. Do not assume the Windows sample configuration will work unchanged.

The Linux archive is intended for evaluation, not as a claim of supported or
validated Linux operation. macOS is not currently released.

### From source

- Python 3.11 or later.
- Install Python dependencies with `python -m pip install -r requirements.txt`.
- A working GrandOrgue installation and MIDI setup.

## GrandOrgue, organ, and sample set

The bridge integrates with an existing GrandOrgue installation; it does not replace
GrandOrgue's installation, audio configuration, or organ-loading workflow. Install
GrandOrgue from its [official download page](https://grandorgue.com/download/) or
consult the [GrandOrgue project](https://github.com/GrandOrgue/grandorgue) and its
[community discussions](https://github.com/GrandOrgue/grandorgue/discussions).

The initial fully mapped profile is the **Friesach Parish Church** sample set by
[Piotr Grabowski](https://piotrgrabowski.pl/friesach/). On the Friesach page, choose
the full free version and complete the free checkout to receive the download link.
The sample set is not included in this repository. The full 24-bit version needs
about 13 GB of free RAM for all release samples; the 16-bit version needs about
6.6 GB.

Other organs require their own tested stop/switch paths, MIDI settings, organ file,
and combinations. Do not assume the Friesach mappings apply to another organ.

## Tested setup

The stable Windows release has been tested on this setup:

- GrandOrgue v3.17.3-1.
- Arturia KeyLab Essential 61 mk2, firmware 1.1.10, in DAW mode.
- Windows 11; Python 3.13 when running from source.
- loopMIDI ports `GO2Bridge` and `Bridge2GO`.

This is one hardware setup. Pad numbering and some DAW-mode behavior may vary
between keyboard models or firmware versions; see
[KeyLab GrandOrgue hardware settings](KeyLab_GrandOrgue_HardwareSettings.md).

## Windows installation and setup

Download the Windows installer from the [v2.0.3 stable release](https://github.com/MackyBMC/GrandOrgue-Keylabs-Essential-SimpleConsole/releases/tag/v2.0.3)
and verify it with that release's `SHA256SUMS.txt`. The installer offers:

1. **Standard:** program files are installed separately; settings and takes live in
   `%APPDATA%\KeyLabGrandOrgue`.
2. **Portable:** program and settings live together in the selected folder, marked
   by a `portable.flag` file.
3. **GrandOrgue folder:** choose where your `Organs`, `Settings`, and
   `Combinations` live. The selected path is stored in `go_folder.txt`.
4. **Optional starter files:** copy the provided combinations and MIDI settings
   without overwriting existing files.

Uninstalling removes the program but keeps user settings, takes, and the GrandOrgue
data folder. The v2 installer is separate from v1.0. Unsigned executables may prompt
Windows SmartScreen or antivirus warnings; the release provides checksums.

### GrandOrgue MIDI setup

In GrandOrgue, open **Audio/MIDI > Settings > MIDI Devices** and enable the KeyLab
**MAIN** input and the virtual cable as both an input and an output. Leave the
KeyLab **DAW** input disabled in GrandOrgue: its button messages are ordinary notes
and could sound pipes. The bridge reads that port. Put the keyboard in DAW mode by
pressing the **DAW** pad.

The bridge does not open the KeyLab MAIN port by default, allowing GrandOrgue to
continue receiving keyboard, pedal, and wheel input. Pad presses require a MIDI
splitter or shared-input service if GrandOrgue already owns that port; the bridge
can still drive the pad lights.

### Quick start

1. Connect the KeyLab and start GrandOrgue.
2. Create the loopMIDI ports `GO2Bridge` and `Bridge2GO`.
3. Import the MIDI settings into GrandOrgue (see [Importing MIDI settings](#importing-midi-settings)).
4. Start **KeyLab GrandOrgue Bridge**, select the MIDI ports in settings, and press
   the keyboard's **DAW** pad.

For a controller walkthrough, see the [KeyLab first-run tutorial](docs/KEYLAB_FIRST_RUN.md).

## Linux evaluation notes

The [v2.0.3 release](https://github.com/MackyBMC/GrandOrgue-Keylabs-Essential-SimpleConsole/releases/tag/v2.0.3)
includes an experimental Linux standalone build, but it is not a tested Linux installation guide.
GrandOrgue should be installed and working first. The bridge's `--list` option can
show the MIDI port names visible to it; configure the port-name fragments in
`config.yaml` to match the system. ALSA/RtMidi names can include client and port
numbers that change between sessions, so prefer a stable name fragment over a
numeric identifier.

The app stores its settings under `$XDG_CONFIG_HOME/KeyLabGrandOrgue`, or
`~/.config/KeyLabGrandOrgue` when `XDG_CONFIG_HOME` is unset. GrandOrgue's data
directory and virtual MIDI routing may be configured differently by each distro
and desktop. The bridge currently expects MIDI endpoints to be available; the
Linux build does not create them automatically. Confirm input, output, feedback,
organ startup, and audio independently before relying on it.

GrandOrgue's Linux installation notes recommend X11 because some window
positioning/sizing may not work correctly under Wayland. See the official
[GrandOrgue Linux installation instructions](https://github.com/GrandOrgue/grandorgue/blob/master/INSTALL.md).

## Configuration and MIDI settings

`config.yaml` contains the Friesach profile and the port-name fragments. Important
settings include:

- `organ_path`: the GrandOrgue organ file.
- `ports.go` and `ports.go_out`: virtual MIDI connections between the bridge and
  GrandOrgue.
- `ports.keylab_in`, `ports.keylab_out`, and `ports.keylab_main_in`: KeyLab DAW,
  output, and MAIN port-name fragments.
- `ports.relay_main_out` and `ports.relay_main_in`: optional relay when the bridge
  must read MAIN and GrandOrgue cannot share that input.
- `faders.threshold`, `display.*`, `pads.*`, and `controls.*`: control, LED, and
  display behavior.

The checked-in Windows sample uses loopMIDI names; change them to the actual port
names on other systems. Command-line options override `config.yaml`.

GrandOrgue's MIDI Objects **Import** may clear objects not present in the imported
file. Do not import the checked-in `Settings/Friesach-midi-settings-KeyLab.yaml`
without first protecting your current setup. Instead:

1. Export your current GrandOrgue MIDI settings.
2. Merge the bridge assignments into that export:

   ```text
   python make_go_midi_import.py your-export.yaml merged.yaml
   ```

3. Import `merged.yaml` in GrandOrgue.
4. Check the GrandOrgue log for unused MIDI object paths.

The assignments target the Friesach sample set. Another organ needs its own
verified object paths and mappings.

## Running from source and troubleshooting

Run `python keylab_go_bridge.py` from the repository. Useful options:

- `--list` lists the available MIDI ports.
- `--verbose` prints MIDI diagnostics.
- `--learn-pads` helps identify pad CC numbers.
- `--test-stop 11 --test-off` switches a stop off without moving a fader; run again
  without `--test-off` to switch it back on.

If the LCD stays blank, try the other KeyLab output port with `--kl-out`. If pad
presses do nothing, check that MAIN input sharing or splitting is configured.

## What's new in Version 2

Version 2 turns the bridge into a standalone desktop application:

- **Application and installer:** Nuitka standalone build, Windows Standard and
  Portable installation modes, per-user settings, and optional copy of starter
  combinations and MIDI settings.
- **Paths:** settings, takes, and window layout use the per-user data folder for an
  installed build, the program folder in portable mode, or the source folder when
  running from source.
- **Qt GUI:** global themes, icon packs, and remembered window positions and sizes.
- **Stave Station:** MIDI-to-score editing and engraving, including piano roll,
  voices, lyrics, tonic sol-fa, fingerings, staff labels, and track selection.
- **Take recorder and player:** playback uses a dedicated realtime-priority thread.
- **Release workflow:** GitHub Actions builds versioned assets and publishes checksums.
  Linux-only prerelease tags build Linux without launching Windows or macOS jobs.
- **Repository changes:** application source moved from the old `Scripts/` layout to
  the repository root. The legacy launchers, sniffer, and LED-test scripts are no
  longer in the current tree; the v1.0 tags remain available for those files.

### v2.0.1 maintenance changes

- Fixed installed builds so setter combinations load and save from the configured
  GrandOrgue data folder.
- Start GrandOrgue with the configured organ when the GUI launches.
- Include Matplotlib in the Nuitka standalone build and derive installer version
  from the application's version metadata.

The current `v2.0.3` release includes the new MIDI editing features and an
experimental Linux package. Earlier Linux prereleases remain available in the
release history. See [CHANGELOG.md](CHANGELOG.md) for details.

## Known limits

- The project has been tested on one KeyLab/Windows setup.
- GrandOrgue can only play a MIDI file that is already loaded through its own menu.
- Loading a file returns the registration to step 0.
- KeyLab pad colors may drift; the bridge re-sends them regularly.
- In DAW mode, pads 4 and 5 share a CC; very long presses of pad 5 may be read as
  pad 4.
- Accented letters in combination file names may not display correctly on the LCD.
- The Friesach organ definition wires its tremulants unusually: Tremolo II is not
  connected to its own tremulant, and Tremolo III only works while the Blower switch
  is on. See the hardware control reference.
- Linux is experimental and unvalidated with real hardware; macOS is deferred.
- Executables are unsigned; Windows SmartScreen or antivirus may warn.

## Building and contributing

```powershell
git clone https://github.com/MackyBMC/GrandOrgue-Keylabs-Essential-SimpleConsole
cd GrandOrgue-Keylabs-Essential-SimpleConsole
python -m pip install -r requirements.txt -r requirements-build.txt
python keylab_go_bridge.py
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
```

The Windows build uses Nuitka and Inno Setup 6. Release steps are documented in
[docs/RELEASING.md](docs/RELEASING.md). Linux and macOS packaging status is described
above; macOS is not currently released.

Bug reports, feature requests, and contributions are welcome. Include the operating
system, GrandOrgue version, KeyLab model/firmware, MIDI port names, and steps to
reproduce an issue. Review live-performance changes carefully and keep backups of
GrandOrgue settings and registration data.

## Acknowledgements and project history

This project grew from work exploring the Arturia KeyLab's DAW controls and MIDI
interface. **Ray Juang's**
[flstudio-arturia-keylab-mk2 project](https://github.com/rjuang/flstudio-arturia-keylab-mk2)
was an important reference for understanding the KeyLab display and LEDs; the LCD
frame and LED numbers used here were informed by studying that project. The original
project's [discussion thread](https://forum.image-line.com/viewtopic.php?f=1994&t=243170)
and [community Discord](https://discord.gg/aqA8rnnTFp) remain useful resources for
the underlying KeyLab work.

The author, **MackyBMC**, supplied the organ, keyboard, design direction, and
real-hardware testing. **Claude Sonnet 5** (Anthropic) contributed substantially to
the bridge, MIDI settings generator, diagnostics, documentation, and related tools
through iterative collaboration with the author. The code has only been exercised
on the setup described above; review it before relying on it for live performance.

Thanks also to:

- **Piotr Grabowski** for the Friesach Parish Church sample set.
- **The GrandOrgue project** for its simulator and the source consulted to understand
  MIDI object paths and event formats; no GrandOrgue code is included here.
- **Third-party library authors**; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## License and disclaimer

This project is MIT licensed; see [LICENSE](LICENSE). It is provided as-is, without
warranty or support guarantees. Back up your GrandOrgue settings and organ data.
This project is not affiliated with or endorsed by Arturia, GrandOrgue, Piotr
Grabowski, or Anthropic. KeyLab and Arturia are trademarks of Arturia SA; Claude is
a trademark of Anthropic.
