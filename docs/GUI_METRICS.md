# GUI metrics (gui_metrics.yaml)

The file sits next to `config.yaml`. Appearance > Studio edits it live; it can also be edited by hand. A missing key means its default,
and a rule is only added to the style sheet for a value that differs from the default, so the stock look is unchanged.

## Frames & bevel

| Key | What | Range / choices | Default |
|---|---|---|---|
| `frame_thickness` | Frame thickness - Border width of group boxes, docks, tool bars, tab panes, buttons and input fields. Raised / sunken / groove look best at 2 px or more. | 0..8 px | `1` |
| `frame_style` | Panel bevel - Group boxes, docks, tool bars and tab panes: flat line, raised, sunken, groove (engraved) or ridge. | flat/raised/sunken/groove/ridge | `flat` |
| `button_style` | Button bevel | flat/raised/sunken | `flat` |
| `input_style` | Input field bevel - Text boxes, spin boxes, drop-downs and lists. Sunken is the classic look. | flat/sunken/raised/groove | `flat` |
| `frame_contrast` | Edge contrast - Moves the frame colour towards the text colour: a stronger bevel edge. | 0..100 % | `0` |

## Spacing

| Key | What | Range / choices | Default |
|---|---|---|---|
| `control_spacing` | Tool bar spacing | 0..32 px | `3` |
| `control_padding` | Control padding (vertical) - Space inside buttons and tool bars, above and below the text. | 1..16 px | `3` |
| `control_padding_h` | Button padding (sides) - 0 = automatic. | 0..24 px | `0` |
| `group_padding` | Group box padding - 0 = from the density setting. | 0..20 px | `0` |
| `outer_margin` | Outer window margin - Space between the window edge and its content. | 0..24 px | `0` |
| `tab_padding_h` | Tab padding (sides) - 0 = automatic. | 0..30 px | `0` |
| `tab_gap` | Gap between tabs | 0..12 px | `2` |
| `splitter_width` | Dock separator width | 1..12 px | `3` |
| `scrollbar_width` | Scroll bar width | 6..28 px | `12` |

## Tables & columns

| Key | What | Range / choices | Default |
|---|---|---|---|
| `row_height` | Row height - Lists, trees and tables. 0 = automatic. | 0..48 px | `0` |
| `header_padding` | Column header padding - 0 = automatic. | 0..16 px | `0` |
| `column_offset` | Cell text offset - Indent of the text inside list / table cells and headers. | 0..24 px | `0` |
| `alternate_rows` | Alternating row colours - Every other row of every list and table is tinted. | bool | `False` |
| `alternate_tint` | Row tint strength | 1..30 % | `6` |
| `grid_lines` | Grid lines in tables | bool | `False` |

## Fonts

| Key | What | Range / choices | Default |
|---|---|---|---|
| `ui_font_family` | Interface font | font | `` |
| `ui_font_pt` | Interface font size - 0 = the system size. 'Text size %' on the Theme tab scales it. | 0..24 pt | `0.0` |
| `list_font_family` | List / table font | font | `` |
| `lcd_font_family` | LCD readout font | font | `` |
| `title_weight` | Title weight | 400..900 | `600` |
| `font_hinting` | Font hinting | default/none/vertical/full | `default` |
| `font_smoothing` | Font smoothing | default/off/on | `default` |

## Shadows

| Key | What | Range / choices | Default |
|---|---|---|---|
| `shadow_enabled` | Panel shadows - A soft shadow inside the dock frame (docked and floating). Drawn by the frame itself: no cost for the content. | bool | `False` |
| `shadow_blur` | Shadow size | 0..40 px | `14` |
| `shadow_dx` | Shadow offset right | -12..12 px | `0` |
| `shadow_dy` | Shadow offset down | -12..12 px | `3` |
| `shadow_opacity` | Shadow strength | 0..100 % | `45` |

## Performance & GPU

| Key | What | Range / choices | Default |
|---|---|---|---|
| `perf_preset` | Performance profile - Auto picks Low power / Balanced / High quality from this computer's CPU, memory and graphics. Editing a switch below makes it Custom. | Auto/Low power/Balanced/High quality/Custom | `Auto` |
| `gl_backend` | Graphics backend - Chosen before the window opens. Use Software when the screen flickers or stays black with a graphics driver problem. (restart) | Qt default/Desktop OpenGL/OpenGL ES (ANGLE)/Software | `Qt default` |
| `roll_gpu` | GPU-drawn piano roll - The piano roll is drawn by OpenGL instead of the CPU: smoother scrolling and zoom on a real graphics card. (reopen the roll) | bool | `False` |
| `roll_antialias` | Smooth edges in the roll | bool | `True` |
| `roll_smooth` | Smooth scaling of pictures | bool | `True` |
| `ui_animations` | Menu / tooltip animations | bool | `True` |

## Live console

| Key | What | Range / choices | Default |
|---|---|---|---|
| `live_ratio_1` | Live console: column 1 - Registrations. The three numbers are the proportions of the first run (or a double-click on a column wall). | 1..10 | `4` |
| `live_ratio_2` | Live console: column 2 - Active stops. | 1..10 | `3` |
| `live_ratio_3` | Live console: column 3 - Pads and volumes. | 1..10 | `3` |
| `column_gap` | Live console: column gap | 0..32 px | `7` |
| `side_column_width` | Sheet music: file list width | 220..1200 px | `320` |

## Performance profiles

Auto picks one of these from the CPU threads, memory and graphics adapter. Editing a switch makes the profile Custom.

- **Low power**: roll_gpu=False, roll_antialias=False, roll_smooth=False, ui_animations=False, shadow_enabled=False
- **Balanced**: roll_gpu=False, roll_antialias=True, roll_smooth=True, ui_animations=True, shadow_enabled=False
- **High quality**: roll_gpu=True, roll_antialias=True, roll_smooth=True, ui_animations=True, shadow_enabled=True

## Looks

Flat (default), Raised (classic), Engraved, Compact LCD, Spacious (touch)
