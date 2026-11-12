"""Audio mixer backend: per-application volume of the Windows output (GrandOrgue, a media player with orchestral takes, ...).

CHANGELOG
2026-11-12  New. Windows only (pycaw / Core Audio session volumes). Strips = running audio applications + the master volume of the default
            output. Scenes (named sets of levels per application, e.g. "Interlude", "Service") are kept in mixer_scenes.json next to config.yaml.
            Nothing here touches MIDI or the organ's own (GrandOrgue) volume settings: it only moves the Windows volume of each program.
"""
import json
import os


class Strip:
    def __init__(self, key, name, volume, muted):
        self.key, self.name, self.volume, self.muted = key, name, float(volume), bool(muted)


class PycawBackend:
    """Per-application volumes through Windows Core Audio. available() says why not when it cannot work."""
    MASTER = "__master__"

    def __init__(self):
        self.reason = ""
        self._sessions = {}
        try:
            from pycaw.pycaw import AudioUtilities               # noqa: F401
        except Exception as exc:                                  # not Windows / not installed
            self.reason = f"The audio mixer needs Windows and the pycaw package (pip install pycaw). ({type(exc).__name__})"

    def available(self):
        return not self.reason

    def _master(self):
        from pycaw.pycaw import AudioUtilities
        speakers = AudioUtilities.GetSpeakers()
        endpoint = getattr(speakers, "EndpointVolume", None)      # newer pycaw
        if endpoint is not None:
            return endpoint
        from comtypes import CLSCTX_ALL
        from ctypes import POINTER, cast
        from pycaw.pycaw import IAudioEndpointVolume
        return cast(speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None), POINTER(IAudioEndpointVolume))

    def strips(self):
        from pycaw.pycaw import AudioUtilities
        out, self._sessions = [], {}
        try:
            master = self._master()
            out.append(Strip(self.MASTER, "Master (output)", master.GetMasterVolumeLevelScalar(), master.GetMute()))
        except Exception:
            pass
        for session in AudioUtilities.GetAllSessions():
            try:
                process = session.Process
                name = (process.name() if process is not None else "") or session.DisplayName or "System sounds"
                if name.lower().endswith(".exe"):
                    name = name[:-4]
                key = f"{name.lower()}#{session.ProcessId}"
                volume = session.SimpleAudioVolume
                self._sessions[key] = volume
                out.append(Strip(key, name, volume.GetMasterVolume(), volume.GetMute()))
            except Exception:
                continue
        return out

    def set_volume(self, key, value):
        value = max(0.0, min(1.0, float(value)))
        if key == self.MASTER:
            self._master().SetMasterVolumeLevelScalar(value, None)
        elif key in self._sessions:
            self._sessions[key].SetMasterVolume(value, None)

    def set_mute(self, key, muted):
        if key == self.MASTER:
            self._master().SetMute(1 if muted else 0, None)
        elif key in self._sessions:
            self._sessions[key].SetMute(1 if muted else 0, None)


def app_name(key):
    return key.split("#")[0]


class Scenes:
    """Named sets of levels per application name, stored as JSON."""

    def __init__(self, path):
        self.path = path
        self.data = {}
        try:
            with open(path, encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                self.data = loaded
        except (OSError, ValueError):
            pass

    def names(self):
        return sorted(self.data)

    def save(self, name, strips):
        self.data[name] = {app_name(s.key): {"v": round(s.volume, 3), "m": bool(s.muted)} for s in strips}
        self._write()

    def delete(self, name):
        self.data.pop(name, None)
        self._write()

    def levels(self, name):
        return self.data.get(name, {})

    def _write(self):
        try:
            with open(self.path + ".tmp", "w", encoding="utf-8") as handle:
                json.dump(self.data, handle, indent=1)
            os.replace(self.path + ".tmp", self.path)
        except OSError:
            pass
