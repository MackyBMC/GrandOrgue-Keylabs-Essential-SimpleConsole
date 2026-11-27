# Changelog

## Unreleased

### New
- One "Open MIDI / take" picker (recordings first, Browse... for others) in the main window, Stave Station and Piano Roll; the Stave Station's takes list now reads the bridge's MIDI folder, so recordings appear there.
- Stave Station picks the default layout from the notes: one clef -> solo, both -> grand staff, pedal-range voice -> organ + pedal, four voices -> choir, more -> one stave per track.
- Tracks: Organ column always shows manual + registration; Instrument defaults to the registration / setter name; right-click Instrument or Organ for choices.
- Theme choices: the floating LCD colour schemes ("LCD ...") are app themes too.
- Tracks: per-column alignment (right-click the header); Instrument is editable; Organ column shows the registration in short form, full names on hover.
- Piano Roll: compact tempo control (one row, options under the ... menu).
- KeyLab Record key LED (id 95) lights while recording or counting in.

### Fixed
- Piano Roll: a loaded file is zoomed and centred on its notes (no more scrolling down from C9).
- Opening a take in the editor no longer stops the playback that has just started (Record center Play / Stop; the editor seemed dead after opening recordings).
- Piano Roll: Play of a recorded take no longer shows the playhead one lead-in (about a bar) ahead of the audio.
- Tracks: column alignment now covers every cell, not only the header.
- Piano Roll: a loaded file scrolls to bar 1 (no empty gap after the keys). Dock resize grip sits 3 px further in.
- Floating dock: the dotted resize grip sits in the real bottom-right corner.
- Record center: Open in roll loads the take into the roll at once; Play / Stop shows what is playing, or why it could not start.

### Changed
- Internal: 11 widget / dialog classes and the config editor moved from qt_gui.py to the new gui/ package (no behaviour change).
- Internal: ActiveTickDelegate flag clearing rewritten so pyright is clean (same behaviour).
- Internal: SheetMusicWindow moved to gui/sheet_music.py; it no longer imports the main window (parent check via a Protocol).
- Internal: Stave editor widgets and dialogs moved from midi_stave.py to score_widgets.py, roll_widgets.py and stave_dialogs.py (no behaviour change).
- Docks use the floating LCD's frame (grey, thin accent line, darker panel, small margin, corner grip when floating); the Record center is a plain widget with tight margins and the main-window dock separators are thin, so no space is wasted around the Velocity lane and the Record center.
- Compact frames, in the style of the floating LCD: group boxes, dock titles and tabs use much less space (the Density setting drives it; Compact is the new default, Appearance... changes it). Docks get a slim title bar (float and close buttons, double-click floats / docks) and a floating dock can be made translucent from its right-click menu (remembered).
- The one-off apply scripts used while the tree diverged (add_record_center, record_center_v2 / v3, apply_copyright, fix_about, hide_padmap, wiki_apply_to_organ) are removed from the repository; their changes are in the code.

## 2.0.9-32 (2026-11-21)

### New
- Record center: a selected take is plotted above the list (each channel / part in its own colour, play position) and a finished take is selected for checking. The KeyLab LCD, the LCD in the window and the floating LCD all show the recording state (REC time, notes, STEP / PART, COUNT-IN, REC stopped); the KeyLab Stop button ends a recording or cancels the count-in.
- Piano Roll: the Record center is a dock (drag, float, resize, close; View menu brings it back; layout remembered), has a count-in (1 or 2 bars of metronome clicks) and Play / Stop for a listed take. dock_helper.dock_in() is the standard way to dock a panel.
- Piano Roll: Record center under the roll - Record / Stop, a live plot of the running take, step-by-step input (Rest / Back), new parts added to the loaded MIDI on the next free channel (a live part plays the loaded MIDI along) and a list of takes (open, play, rename, delete to _trash). One record engine: the same one as the KeyLab Record key.
- Organ Setter Wiki: "Apply to organ" draws the stops of the edited step on the live organ (only stops that differ are toggled) so it can be heard before saving.
- Organ Setter Wiki: the empty PAD MAP strip is hidden above the stop editor.
- Copyright: Basil Mc Helm is named as the copyright holder in LICENSE, Help > About, the README, the Windows executable properties and the installer publisher.
- **Organ Setter Wiki** (the former Setter Editing tab) in four frames that remember their sizes: setter-file dropdown with previous / next and the guide top left, the organ's picture top right, the stop editor of the chosen step bottom left, the heuristic reading bottom right.
- Setter dropdown: move to any setter file, independent of the setter that is live in GrandOrgue; the list follows the filters (period, tradition, composer, stars, "suits this organ").
- Setter guides: each setter can carry a guide with 0-5 stars for baroque, classical, romantic and modern and for catholic, early protestant and modern church traditions, composers, the reason for the registration and layering notes. Stored as `Guides/<set>/<setter>.guide.yaml` outside the Combinations folder so GrandOrgue never reads them; read from the GrandOrgue data folder and also from the project's `Guides/<set>/`, saved to the data folder.
- Ratings are five clickable stars drawn in the theme's accent colour (click the current rating again to clear).
- Organ character: what an organ was built for (builder, year, stop count, ratings, layering) is kept in its organ map and edited in the same panel. Friesach and Cracow are filled in the first time from the sample makers' pages; existing text is kept.
- Organ picture: the first image the `.organ` file refers to, or "Choose picture..." (remembered per organ).
- Heuristic reading: for the selected stops, stop-family counts and 0-5 stars per period and tradition (from stop names and footage), shown beside the guide's own ratings and a "suits this organ" rating. A hint, not a verdict.
- Stop editor on the wiki: edit a step's stops, "Take live stops", "Revert", "Save setter".
- Organ FAQ (`docs/ORGAN_FAQ.md`): history, regions, liturgy and registration as questions and answers. Opens as plain reading; "Edit" shows a Markdown editor with toolbar and live preview, saved as a copy in the data folder, "Reset" returns to the shipped text.
- Add organ also maps the active organ's default setters (Friesach's set) onto the new organ as well as the stop names allow, using the combination alias file, and writes them in GrandOrgue's format.
- Combination Files tab: "Tag for deletion", "Untag" and "Remove tagged files" (tagged files are struck through; removing moves them to `Combinations/_trash/`, recoverable). A failing setter save now logs the reason.
- "Add organ" (Organ Selection tab): bring in another organ from its `.organ` file alone, no MIDI export needed. It writes the layout file, the organ map, the setter folder and the GrandOrgue MIDI settings to import (`Settings/<organ> midi import.yaml`); the organ then appears under "Known organs", and "Use this organ" also switches the layout file. The active organ is not touched.
- Organ map, stage 2: screen and snapshot names come from the map's display names in the chosen language (`display: {default, en, de, af ...}`; the LCD takes the first 16 characters; `lcd_names` in the config still win), setter files carry the organ's exact names, the setter names matrix is now a `setters:` section of the map (the old `Settings/<organ>.names.yaml` is merged in once), and the map lists the organs you can switch to (`organ_maps` in the snapshot; selecting one sets the organ file and setter set, effective at the next start).
- Organ map (`Organs/<organ>.map.yaml`, one per organ): the bridge's own keys (P1, H3, Cp1.2, T1 ...) linked to the organ's ids and its exact GrandOrgue names, with display names per language. Setter files take every name from the map, so names cannot drift; a different organ is a different map. Built from the organ file the first time and kept (display names you edit stay).

### Fixed
- A setter saved by the bridge could be rejected by GrandOrgue ("Wrong name ... instead of ..."): the bridge wrote its 16-character LCD stop names. Setter files now use the full names from the organ file, and setter files already saved with cut-short names are repaired silently (folder backed up first).
- Release versions can be `X.Y.Z` or `X.Y.Z-N` with optional letters (`2.0.9-1`, `2.0.9-1a`); the Windows executable gets a four-number file version (`2.0.9.101`) and only `-linux.N` tags are marked pre-release.

## 2.0.9 (2026-11-20)

### GrandOrgue: tempo, setters and names
- One session BPM for everything (default 80 like GrandOrgue, range 1-500): the bridge, Stave Station, Piano Roll and the GrandOrgue metronome follow it. The metronome is driven through GrandOrgue's own BPM +1/-1/+10/-10 buttons; the MIDI file player shows whether GrandOrgue's BPM is in sync. New takes are stamped with the BPM they were recorded at, so they play back at the speed you played them.
- The GrandOrgue metronome BPM label path is "Metronome/Metronome BPM" (the Friesach MIDI settings were updated; re-import them in GrandOrgue).
- Setter tick you can trust: a setter is ticked only when GrandOrgue itself reports the same file and step and every stop the setter switches on. The tick appears as soon as that is confirmed, and the setter GrandOrgue remembered is ticked when the bridge starts ("F+ S?/n": file/step proven, stops assumed, because GrandOrgue only reports changes).
- Setter list "Status" column in short hand: "F+ S5/7" (F+ file/step confirmed, F? settling or cued, Fx another file/step; S = stops confirmed ON of those the setter switches on); the tooltip names the stops not confirmed. The console says why a setter is not verified.
- Setter files are read with decimal ids (PyYAML's octal reading turned 010 into 8 and 011 into 9) and compared with GrandOrgue's 7-bit, 32-character file label (accents become "_", so "Récit doux" matched nothing).
- Names matrix (`Settings/<organ>.names.yaml`): every setter file gets a GrandOrgue-safe ASCII name of at most 32 characters while the nice, multilingual display names live in the matrix. Older setter folders are repaired silently on load (renamed files, original names kept as aliases, folder backed up to `Combinations/_backup/`); saved MIDI markers and projects that name an old file follow the rename.
- Setter file format: files are written the way GrandOrgue writes them (zero-padded text keys, every step complete, Blower / Ambient, switch entries next to stop entries). Files the older bridge saved in a broken format are rebuilt by label, silently, with a backup.
- GrandOrgue sorts its setter files case-sensitively; the bridge now uses the same order, so jumping to a setter after a rename lands on the right file.
- GrandOrgue MIDI settings are read with leading-zero paths kept as text ("047" no longer becomes 39), which fixed the "Unused MIDI object path" warnings and the unconfirmed Tremulant 2 / 3 Man items.
- Saving a setter presses GrandOrgue's RefreshFiles so a new file appears in its list. The Friesach MIDI settings carry the Sequencer/RefreshFiles route (CC 16, channel 16); re-import them in GrandOrgue.
- Selecting a setter refreshes GrandOrgue's cached combination-file list before loading it.
- Record-button MIDI takes now capture and use the session BPM when recording starts.
- Type the optional GrandOrgue metronome BPM feedback value.
- File > "Export for GrandOrgue (native MIDI)...": writes the loaded MIDI (with stave / roll edits, setters and registrations) as a GrandOrgue-format recording whose stop on / off events are inside the file, so GrandOrgue's own MIDI player switches the stops without the bridge.

### New
- Pylance fixes in Stave Station MusicXML parsing: optional stave fields, Score/Part/Opus narrowing, and explicit Note/Chord handling.
- Shared MIDI transport Play / Pause now resumes from the saved file position; Stop rewinds and the Stave / Piano Roll edited-score controls use the same pause state.
- Registration bank: pads scale with the text and stay centred; the marks are gone; the bank is a list; Cat/Char starts the jog on it (then on to the Active registrations, buttons and tick boxes, cycling); click an active registration to switch it off, again to switch it on.
- View > "Play stave edits in the main window": choose whether Play uses the original MIDI (default) or the stave / roll edits.
- Fluid columns in every list/table; Ctrl+M toggles the Mixer reliably (Piano Roll import is Ctrl+Shift+I); sheet music folders of page images convert to a PDF.
- Docked LCD height is fluid: it shares the window height with the tabs and shrinks with the window (minimum 90 px instead of 260).
- Help > Licenses shows the full THIRD_PARTY_NOTICES.md inside the app; Help > About carries the visible Verovio / Qt / music21 credits.
- Recording a MIDI that has unsaved stave / piano-roll edits asks first: Save edited MIDI / Don't save / Cancel. Recording shows as a red "Recording..." on every transport, and the controller's record button starts it.
- "Quantised" toggle on every transport (one shared setting, the stave's "Play what the stave shows"): Play on a MIDI with note edits plays the stave version (on) or the notes as played (off); unedited files still play the file itself.
- A small piano roll of the loaded MIDI (colour = MIDI channel) shows under "Loaded: <name>" in the MIDI player; double-click opens it in the Piano Roll tab.
- Stop Selection Grid popup stays inside the screen and no longer overshoots (fixes the endless setGeometry warnings).
- VS Code task "11. Answer Claude chat questions" launches the dev-only Claude question-answering tool with the repository's build virtual environment.
- Stave Station project file (`.ss`, plain YAML) saved next to the MIDI as you work: every setting, bar lines and per-bar grids, track / manual mapping, setters, division labels, pedal marks, words and (only if you edited them) the piano-roll notes. Reopening the MIDI or the `.ss` brings it all back. The MIDI is linked (relative path, absolute path, size, SHA-1), never changed. Open project... / Save project as... in the Recording box. Words moved from `<file>.lyrics.json` into the project (old files are still read).

- KeyLab controller toggle in the main window tool bar: disengage the controller from the bridge at any time (its MIDI ports close, nothing waits for it, GrandOrgue keeps playing) and engage it again. Remembered across restarts in `controller_engaged.txt` (default engaged; `controller_engaged:` in config.yaml sets the first-run default).
- LCD dock: right-click the floating LCD > "Dock into the main window" puts it in the main window's LCD panel, replacing the fixed 2-line LCD; "LCD float" or right-click > Undock pops it out again. Remembered between runs. Also fixes a TypeError when the LCD was closed.
- One MIDI everywhere: the file loaded in the main window (Open MIDI, jog, Previous / Next) is opened in the stave editor and piano roll too, and a file or `.ss` project opened in the stave editor becomes the main window's file. The editor follows after 0.9 s of stillness and only while it is open.
- One merged menu bar (File / Edit / Select / View / Zoom / Layout / Window / Help), always complete; Stave Station and Piano Roll items are merged in and dimmed unless their tab is showing. Top-level tabs Bridge (with the old Live / Main ... Organ Selection tabs as sub tabs) / Stave Station / Piano Roll; the KeyLab LCD panel collapses (the floating LCD pops up instead).
- Transport split into two framed groups: "Setter / registration (KeyLab keys)" in blue (Rewind, Forward, Jog turn, Jog press) and "MIDI file player" in orange (Play, Stop, Loop, Metronome, Save, Open MIDI, tempo, channels, position). Each setter button names its KeyLab key.
- One shared MIDI transport (Play / Pause, Stop / Panic, Loop, Metronome, Save, position, loaded file) in the main window, the stave editor and the piano roll; every copy drives the one MIDI take of the app. The main window's right-hand column scrolls instead of squashing buttons.
- The bridge only connects to the KeyLab when it is detected at start; otherwise it runs without it and the "KeyLab controller" toggle stays dim until a KeyLab port appears.
- Launch checks: a second bridge says "already running" and exits; GrandOrgue is not started again when it is already running (a notice instead).
- Mixer: a floating / dockable frame (View > Mixer, Ctrl+M) with graduated vertical faders (ticks every 5 %, numbers every 10 %, dB readout) for the Windows volume and mute of each program that plays sound (GrandOrgue, the orchestral background player) plus the master, with named scenes (Interlude / Service). Fixed-size strips, never stretched; stays available on every tab. Needs `pycaw` (Windows).
- Scaling: "Text size %" (60-160 %) now scales paddings, scroll bars, tabs, menus, slider handles and check marks with the text, control heights follow the font, the main window can shrink to 560 x 420, the top bar wraps onto a second row instead of clipping its buttons, and the Live page has one scroll bar that only appears when even the smallest layout does not fit.
- Piano roll snapping like FL Studio: snap on by default (new option "Note length"), notes follow the snap live while placing, moving and resizing either end; hold Alt for free.
- `pyrightconfig.json` (Windows platform, basic checking) and type-clean optional-library imports, so Pylance shows no errors for `audio_tap.py`, `audio_mixer.py` and the new files.
- Live page: the walls between the setter list, the stops column and the transport column can be dragged to resize them (remembered; double-click a wall for the default widths).

### Licensing
- Development-operations files (assistant question/answer exchange files, tools/, .kilo/, .vscode/) are no longer published: ignored by git and excluded from the licence by a scope statement in the README.
- THIRD_PARTY_NOTICES.md: Qt PDF licence and its PDFium components, Verovio credit requirement, the reference project's MIT notice with its copyright line, and the music21 corpus caveat.
- THIRD_PARTY_NOTICES.md rewritten: every bundled component with its licence, the LGPL conditions for Qt and Verovio, the music21 corpus caveat (some bundled encodings are non-commercial), Font Awesome and Apache attributions, the reference project, and a list of items still to verify.

### Fixed
- Fixed the Pylance-reported attribute, optional-value and type errors in `qt_gui.py` by clarifying dynamic imports, widget types and nullable UI state.
- Piano Roll tab crashed with `module 'midi_stave' has no attribute 'PianoKeys'` inside the bridge (the bare `import midi_stave` found the folder, not the module); the roll window and the track organ dialog now use the module their Stave came from.
- Stave builder follows engraving practice (Gould, "Behind Bars"): notes are split into tied pieces so none crosses the middle of the bar (4/4 half note on beat 2 is two tied quarters) or a beat it may not cross; 6/8 and 12/8 keep their dotted beats; rests follow the same boundaries (no dotted rests in simple time, none across the half bar).
- Chromatic notes are spelled by direction (C C# D D# E, then E Eb D Db) instead of one fixed sharp/flat table.
- Slurs no longer run over chords or notes longer than two beats, cover at most 8 beats, and end on the last piece of a tied note.
- Not changed: spacing, accidental stacking, stems, beams, voice collisions and system justification are Verovio's own and already follow these rules.

## 2.0.8

### New
- LCD float v2: transport, recording and metronome icons with clocks; live volume knobs and swell fader (drag or wheel to set); spectrum or oscilloscope of the output sound (needs PyAudioWPatch); colour schemes plus custom colours; jog-list badge.
- Cat/Char in the sheet music window is shown on every LCD (message plus an F / S marker).
- LCD float: always-on-top vintage-style LCD panel (toolbar "LCD float") with the setter, step, and drawn stops by division; drag, right-click for size / opacity / compact.
- Sheet-music cue and file navigation can be controlled by the sustain pedal, with a clearer LCD cue preview.
- Long LCD messages scroll so the full text can be read.
- Session-wide BPM target with synchronized, graded faders and shared undo / redo in the Bridge, Stave, and Piano Roll windows.
- Playback scales each file's tempo map to the selected BPM; GrandOrgue metronome tempo feedback and tempo-step controls follow the same target.
- MIDI, karaoke MIDI, and MusicXML exports save the selected tempo; changing the session tempo alone does not rewrite files.
- Opening a file sets the BPM to the file's own average tempo; the stave editor's play preview keeps the chosen BPM.
- Organ dialog, track list and stave rows show the organ's own manual names (Great / Swell / Choir, German, French, custom); the saved mapping is unchanged.

### Fixed
- Dev deployment preserves target venvs; `-Pip` installs requirements into the deployed `.venv-build`, and `-Run` launches with that interpreter.
- MIDI file playback no longer drifts slow or catches up in bursts: absolute schedule, stalls absorbed, output queue wakes at once. The playback log now reports the worst lateness.
- Stave editor score follow keeps the playing bar in view and restarts cleanly after Stop.
- Sheet music: >> / << scroll a zoomed page by one screenful, then turn to the next page at the same zoom (<< walks back up). Zoom + / - start from the zoom on screen. Two-page view no longer opens blank.
- Textual console: restored Rich markup escaping (the last cleanup removed it, so `[` in LCD / log text could break the console).
- Textual console: type the Rich escape wrapper and key bindings for Pylance without changing footer visibility or shortcuts.
- Jog / LCD sync: setters sharing a name and step are resolved to the one nearest the last position, not always the first.
- Personal files (`last_dirs.json`, `preset_activation.txt`) are ignored by git.
- ODF scanning types missing switch/stop references as optional integers, clearing the two Pylance argument-type diagnostics.
- Choosing German / French / Custom manual names (or changing the manual count / pedal) now updates the stave and track list; before, only a hint changed.
- Playhead, timeline and step-sequence length follow the playback BPM.

## 2.0.3

### New
- **MIDI Track / Piano Roll Editor.** The piano roll window has a track list: active track (new notes and piano keys use its channel), show / hide, editable track names (the stave titles follow), channel, instrument, note count, add and remove track.
- **Stave shows: Quantised or Raw.** Choose whether the stave is built from the quantised timing or from the notes as played (32nd-note grid, no gap closing). The MIDI itself is never changed by this choice.
- **Shape MIDI timing** (Edit menu, Ctrl+Q, or the Quantise panel): grid or fixed-millisecond quantise, strength, swing, humanise, snap note ends or legato / slur, finger-numbered notes joined legato, organ-friendly gap closing for piano-style MIDI, limited to a MIDI-note range or the selection, with restore of the original timing. Finger and pedal marks follow their notes when they are re-timed.

- **Piano roll view.** Keys taller / shorter on Ctrl+Up / Ctrl+Down; the grid and key rows fill the whole roll window and cover the full keyboard (the vertical scroll bar now has somewhere to go); a **Layout** menu saves and restores named layouts (zoom, snap, grid, panels, window and toolbars) and the roll reopens as you left it.

- **Piano roll shows the tracks.** Each track has its own colour (the same dot colour as in the Tracks list); unticking a track hides its notes in the roll; the active track is full strength and the others fade (View menu: "Colour notes by track", "Fade the notes of the other tracks").

- **Track to organ mapping.** The Tracks list has an Organ column and an "Organ..." dialog (double-click the cell): choose the manual(s) a track plays on (its MIDI channel in GrandOrgue), let the editor suggest one from the track name and instrument, and set its registration changes (setters or stops, bar by bar). Playback, MIDI export and the piano keys follow it whatever the stave layout; tracks with no mapping behave as before.

- **Bass to pedal.** In a track's Organ dialog, "Bass to pedal" sends the lowest note of every chord (at or below a MIDI-note limit, default G3) to the Pedal as a mono bass line and the other notes to the ticked manual(s); nothing in the track is changed. "Extract the bass to its own pedal track now" moves those notes into a real new track mapped to the Pedal. "Suggest from the track" offers this for a polyphonic low track.

- **Audition.** Piano keys now sound for as long as the mouse button is held (and slide from key to key while dragged). The new **Audition** button in the roll window puts a line on the roll: click or drag to hear exactly the notes under it, on the manuals each track is mapped to, while the button is held.

- MIDI, XML, MusicXML, and karaoke MIDI assets in the `midi` folder are excluded from version control; the tracked preview MIDI file is removed.

### Fixed
- Ctrl+Up / Ctrl+Down no longer clash: octave up / down moved to Ctrl+Shift+Up / Down (Shift+Up / Down still works on the roll).
- Organ layout file is looked for in the GrandOrgue folder first.
- Piano roll: drag on empty space now rubber-band selects notes (Shift adds, drag to the window edge scrolls).
- Alt + wheel key zoom no longer sticks (Qt swaps the wheel axis with a modifier held); zoom keeps the middle pitch in place.
- Stop grid remembers its position; toolbar icons show short labels with the full wording as the hover tip; piano keys sound when no stave owns the pitch.

## 2.0.2-linux.1 (experimental prerelease)
- First Linux-only prerelease build for evaluation; macOS packaging is deferred to a later release.
- This release does not replace or alter the supported Windows v2.0.1 release.

## 2.0.1
- Fix installed builds loading and saving setter combinations from the configured GrandOrgue data folder.
- Start GrandOrgue with the configured organ when the GUI launches.
- Include matplotlib in the Nuitka standalone build and derive installer version from the built executable.

## 2.0.0
- Stave editor: piano-roll window, voices, rest tidying, fingerings, division labels, tonic sol-fa, lyrics, track selection.
- Global theming (Breeze / Adwaita / Fusion / Nord / ...), icon packs, remembered window positions.
- Installer: per-user data folder, portable mode, GitHub release pipeline.

## 1.0.0
- First release: KeyLab <-> GrandOrgue bridge.
