"""Audio mixer backend: per-application volume of the Windows output (GrandOrgue, a media player with orchestral takes, ...).

CHANGELOG
2026-11-13  Type-clean: pycaw / comtypes are loaded by name (optional()) and the COM objects are typed Any, so Pylance reports nothing when they are
            absent or untyped. Names like "@%SystemRoot%\\...AudioSrv.Dll" are shown as "System sounds".
2026-11-12  New. Windows only (pycaw / Core Audio session volumes). Strips = running audio applications + the master volume of the default
            output. Scenes (named sets of levels per application, e.g. "Interlude", "Service") are kept in mixer_scenes.json next to config.yaml.
            Nothing here touches MIDI or the organ's own (GrandOrgue) volume settings: it only moves the Windows volume of each program.
"""
import importlib
import json
import math
import os
from ctypes import POINTER, cast
from typing import Any, Dict, List, Optional

MASTER = "__master__"


def optional(name: str) -> Any:
    """Import a library by name; None when it is not installed (type checkers see Any, never a missing import)."""
    try:
        return importlib.import_module(name)
    except Exception:
        return None


def to_db(volume: float) -> str:
    """Level readout: 1.0 -> "0.0 dB", 0.5 -> "-6.0 dB", 0 -> "-inf"."""
    return "-inf dB" if volume <= 0.0005 else f"{20.0 * math.log10(volume):+.1f} dB"


class Strip:
    def __init__(self, key: str, name: str, volume: float, muted: bool) -> None:
        self.key = key
        self.name = name
        self.volume = float(volume)
        self.muted = bool(muted)


def app_name(key: str) -> str:
    return key.split("#")[0]


def clean_name(name: str) -> str:
    if name.startswith("@") or not name.strip():
        return "System sounds"
    return name[:-4] if name.lower().endswith(".exe") else name


class PycawBackend:
    """Per-application volumes through Windows Core Audio. available() is False (with .reason) when it cannot work."""

    def __init__(self) -> None:
        self.reason = ""
        self._pycaw: Any = optional("pycaw.pycaw")
        self._volumes: Dict[str, Any] = {}
        self._endpoint: Any = None
        if self._pycaw is None:
            self.reason = "The audio mixer needs Windows and the pycaw package (pip install pycaw)."

    def available(self) -> bool:
        return not self.reason

    def _master(self) -> Any:
        if self._endpoint is None:
            speakers: Any = self._pycaw.AudioUtilities.GetSpeakers()
            endpoint: Any = getattr(speakers, "EndpointVolume", None)         # newer pycaw
            if endpoint is None:                                              # older pycaw: activate the COM interface by hand
                comtypes: Any = optional("comtypes")
                iface: Any = self._pycaw.IAudioEndpointVolume
                raw: Any = speakers.Activate(iface._iid_, comtypes.CLSCTX_ALL, None)
                endpoint = cast(raw, POINTER(iface))
            self._endpoint = endpoint
        return self._endpoint

    def strips(self) -> List[Strip]:
        out: List[Strip] = []
        self._volumes = {}
        try:
            master: Any = self._master()
            out.append(Strip(MASTER, "Master", float(master.GetMasterVolumeLevelScalar()), bool(master.GetMute())))
        except Exception:
            self._endpoint = None
        sessions: Any = self._pycaw.AudioUtilities.GetAllSessions()
        for session in sessions:
            try:
                process: Any = session.Process
                raw_name = (process.name() if process is not None else "") or session.DisplayName or ""
                name = clean_name(str(raw_name))
                key = f"{name.lower()}#{session.ProcessId}"
                volume: Any = session.SimpleAudioVolume
                self._volumes[key] = volume
                out.append(Strip(key, name, float(volume.GetMasterVolume()), bool(volume.GetMute())))
            except Exception:
                continue
        return out

    def set_volume(self, key: str, value: float) -> None:
        value = max(0.0, min(1.0, float(value)))
        if key == MASTER:
            self._master().SetMasterVolumeLevelScalar(value, None)
        elif key in self._volumes:
            self._volumes[key].SetMasterVolume(value, None)

    def set_mute(self, key: str, muted: bool) -> None:
        if key == MASTER:
            self._master().SetMute(1 if muted else 0, None)
        elif key in self._volumes:
            self._volumes[key].SetMute(1 if muted else 0, None)


class Scenes:
    """Named sets of levels per application name, stored as JSON."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.data: Dict[str, Dict[str, Dict[str, Any]]] = {}
        try:
            with open(path, encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                self.data = loaded
        except (OSError, ValueError):
            pass

    def names(self) -> List[str]:
        return sorted(self.data)

    def save(self, name: str, strips: List[Strip]) -> None:
        self.data[name] = {app_name(s.key): {"v": round(s.volume, 3), "m": bool(s.muted)} for s in strips}
        self._write()

    def delete(self, name: str) -> None:
        self.data.pop(name, None)
        self._write()

    def levels(self, name: str) -> Dict[str, Dict[str, Any]]:
        return self.data.get(name, {})

    def _write(self) -> None:
        try:
            with open(self.path + ".tmp", "w", encoding="utf-8") as handle:
                json.dump(self.data, handle, indent=1)
            os.replace(self.path + ".tmp", self.path)
        except OSError:
            pass


def default_backend() -> Optional[PycawBackend]:
    return PycawBackend()
