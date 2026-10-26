"""Logical stop-grid navigation shared by the bridge and GUI."""


class StopGridModel:
    GRID_COLUMNS = 8
    PAD_COLUMNS = 4
    PAD_ROWS = 2
    PAD_COUNT = PAD_COLUMNS * PAD_ROWS
    VISIBLE_KINDS = {"stop", "coupler", "tremulant"}
    HIDDEN_NAME_FRAGMENTS = ("key action", "mixtur minor")

    def __init__(self, items):
        self._item_source = items
        self.focus_x = 0
        self.focus_y = 0

    @property
    def items(self):
        source_items = list(self._item_source)
        panel_stops = {
            (item.division, self._normalized_name(item.name))
            for item in source_items
            if item.kind == "stop" and self._path_category(item.path) == "switches"
            and not self._hidden_name(item.name)
        }
        visible = []
        for item in source_items:
            if item.kind not in self.VISIBLE_KINDS or self._hidden_name(item.name):
                continue
            path_category = self._path_category(item.path)
            if item.kind == "coupler" and path_category != "switches":
                continue
            if (item.kind == "stop" and path_category == "stops"
                    and (item.division, self._normalized_name(item.name)) in panel_stops):
                continue
            visible.append(item)
        return visible

    @staticmethod
    def _path_category(path):
        parts = path.split("/")
        return parts[2] if len(parts) > 3 and parts[0] == "manuals" else ""

    @classmethod
    def _hidden_name(cls, name):
        normalized = cls._normalized_name(name)
        return any(fragment in normalized for fragment in cls.HIDDEN_NAME_FRAGMENTS)

    @staticmethod
    def _normalized_name(name):
        return " ".join(str(name).casefold().split())

    def _grid_rows(self):
        groups = []
        indices = {}
        for item in self.items:
            division = item.division or "Other"
            if division not in indices:
                indices[division] = len(groups)
                groups.append({"name": division, "items": []})
            groups[indices[division]]["items"].append(item)
        rows = []
        for group in groups:
            items = group["items"]
            for row_index, start in enumerate(range(0, len(items), self.GRID_COLUMNS)):
                cells = items[start:start + self.GRID_COLUMNS]
                rows.append({
                    "division": group["name"],
                    "row_in_division": row_index,
                    "cells": cells + [None] * (self.GRID_COLUMNS - len(cells)),
                })
        maximum_y = max(0, len(rows) - self.PAD_ROWS)
        self.focus_y = min(maximum_y, max(0, self.focus_y))
        self.focus_x = min(self.GRID_COLUMNS - self.PAD_COLUMNS, max(0, self.focus_x))
        return rows

    def move_horizontal(self, direction):
        self._grid_rows()
        updated = min(self.GRID_COLUMNS - self.PAD_COLUMNS,
                      max(0, self.focus_x + (1 if direction > 0 else -1)))
        changed = updated != self.focus_x
        self.focus_x = updated
        return changed

    def move_vertical(self, direction):
        rows = self._grid_rows()
        updated = min(max(0, len(rows) - self.PAD_ROWS),
                      max(0, self.focus_y + (1 if direction > 0 else -1)))
        changed = updated != self.focus_y
        self.focus_y = updated
        return changed

    def window_rows(self):
        rows = self._grid_rows()
        window = []
        for offset in range(self.PAD_ROWS):
            row_index = self.focus_y + offset
            if row_index < len(rows):
                row = rows[row_index]
                window.append({**row, "grid_row": row_index, "focus_x": self.focus_x})
            else:
                window.append({
                    "division": "", "row_in_division": None,
                    "cells": [None] * self.GRID_COLUMNS,
                    "grid_row": row_index, "focus_x": self.focus_x,
                })
        return window

    def mapped_slots(self):
        rows = self._grid_rows()
        slots = []
        for row_offset in range(self.PAD_ROWS):
            row_index = self.focus_y + row_offset
            cells = rows[row_index]["cells"] if row_index < len(rows) else []
            for column in range(self.focus_x, self.focus_x + self.PAD_COLUMNS):
                slots.append(cells[column] if column < len(cells) else None)
        return slots

    def mapped_items(self):
        return [item for item in self.mapped_slots() if item is not None]

    def mapped_paths(self):
        return [item.path if item is not None else None for item in self.mapped_slots()]