# Friesach naming rules (what GrandOrgue checks in a setter file)

GrandOrgue compares every entry in a setter file with the organ's own name for that object and id; a different name rejects the entry ("Wrong name X instead of Y of the switch 009"). The bridge's LCD names (16 characters, division codes such as "(H)") are for display only and never go into a setter file.

| Where in the file | Id | Name |
|---|---|---|
| `manuals/<m>/switches/<id>` | switch index of manual `m` (couplers first, then the panel stops) | the organ's switch name, e.g. `HW  Spitzflöte 4'`, `Coupler 5` |
| `manuals/<m>/stops/<id>` | stop index = switch index minus the manual's offset (Pedal 3, HW 2, SW 1, Solo 0) | the organ's stop name (same text as its switch) |
| `manuals/<m>/couplers/<id>` | coupler index within the manual | the organ's coupler name; Friesach numbers them across the organ: Pedal `Coupler 1-3`, Hauptwerk `Coupler 4-5`, Schwellwerk `Coupler 6` |
| step `tremulants/<id>`, `switches/<id>` | organ-wide ids (Blower 001, Tremulant 2 Man 047, Tremulant 3 Man 053, Ambient 054) | the organ's own name |

Rules the bridge follows:
- Ids are written as zero-padded text (`007`) and read as decimal numbers.
- Names come from the `.organ` file (real `Name=` values only; the scanner's stand-ins such as `Coupler001` are ignored), then from the majority of intact setter files.
- The setter file name is plain ASCII, at most 32 characters; the display name lives in `Settings/<organ>.names.yaml`.
