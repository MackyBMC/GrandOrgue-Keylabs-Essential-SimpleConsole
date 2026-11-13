"""Listens to what the PC is playing (WASAPI loopback of the output device GrandOrgue sounds on) for the floating LCD's
spectrum / oscilloscope. Optional: needs numpy and one of PyAudioWPatch (preferred) or soundcard. Without them the tap
just reports why it is off; nothing else in the program depends on it. Nothing is recorded or stored: only the newest
few thousand samples are kept in memory.

CHANGELOG
2026-11-13  Type-clean (Pylance / pyright): optional libraries (numpy, PyAudioWPatch, soundcard) are loaded through optional() and typed Any, so a
            missing library is a runtime message, never an editor error; the buffer is never None.
2026-11-10  New.
"""
import importlib
import threading
import time
from typing import Any, List, Optional


def optional(name: str) -> Any:
    """Import an optional library by name; None when it is not installed (type checkers then see Any, not a missing import)."""
    try:
        return importlib.import_module(name)
    except ImportError:
        return None


np: Any = optional("numpy")              # None -> the LCD shows "numpy missing"

KEEP = 8192


class AudioTap:
    def __init__(self):
        self.status = "off"                # off | starting | on | message why it is unavailable
        self.rate = 48000
        self.device_name = ""
        self._buf: Any = np.zeros(KEEP, dtype="float32") if np is not None else None
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.last_data = 0.0
        self.peak = 0.0

    # ---- control
    def start(self, device=None):
        if np is None:
            self.status = "numpy missing (pip install numpy)"
            return
        self.stop()
        self._stop.clear()
        self.status = "starting"
        self._thread = threading.Thread(target=self._run, args=(device,), daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.5)
        if not self.status.startswith(("numpy", "no audio", "audio")):
            self.status = "off"

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    # ---- data
    def feed(self, samples):
        """Append mono float samples (-1..1). Also used by tests / other sources."""
        if np is None:
            return
        x = np.asarray(samples, dtype="float32").reshape(-1)
        if x.size == 0:
            return
        x = x[-KEEP:]
        with self._lock:
            if self._buf is None:
                return
            self._buf = np.concatenate((self._buf[x.size:], x))
        self.last_data = time.time()
        self.peak = max(self.peak * 0.9, float(np.abs(x).max()))

    def latest(self, count: int = 2048) -> Any:
        if np is None or self._buf is None:
            return None
        with self._lock:
            return self._buf[-count:].copy()

    def active(self):
        return self.status == "on" and time.time() - self.last_data < 1.0

    # ---- devices
    @staticmethod
    def loopback_devices() -> List[str]:
        """Names of output devices that can be listened to (PyAudioWPatch)."""
        pa: Any = optional("pyaudiowpatch")
        if pa is None:
            return []
        try:
            p = pa.PyAudio()
            try:
                return [d["name"] for d in p.get_loopback_device_info_generator()]
            finally:
                p.terminate()
        except Exception:
            return []

    # ---- capture threads
    def _run(self, device):
        try:
            if optional("pyaudiowpatch") is not None:
                self._run_pyaudio(device)
                return
            if optional("soundcard") is None:
                self.status = "no audio capture library (pip install PyAudioWPatch)"
                return
            self._run_soundcard(device)
        except Exception as exc:
            self.status = f"audio capture failed: {exc}"

    def _run_pyaudio(self, device):
        pa: Any = optional("pyaudiowpatch")
        p = pa.PyAudio()
        stream = None
        try:
            wasapi = p.get_host_api_info_by_type(pa.paWASAPI)
            speakers = p.get_device_info_by_index(wasapi["defaultOutputDevice"])
            loops = list(p.get_loopback_device_info_generator())
            pick = None
            if device:
                pick = next((d for d in loops if device in d["name"]), None)
            if pick is None:
                pick = speakers if speakers.get("isLoopbackDevice") else next(
                    (d for d in loops if speakers["name"] in d["name"]), loops[0] if loops else None)
            if pick is None:
                self.status = "no audio loopback device found"
                return
            channels = max(1, int(pick["maxInputChannels"]))
            self.rate = int(pick["defaultSampleRate"])
            self.device_name = pick["name"]

            def callback(data, _frames, _time, _status):
                x = np.frombuffer(data, dtype="<i2").astype("float32") / 32768.0
                if channels > 1:
                    x = x[: x.size - x.size % channels].reshape(-1, channels).mean(axis=1)
                self.feed(x)
                return (None, pa.paContinue)

            stream = p.open(format=pa.paInt16, channels=channels, rate=self.rate, frames_per_buffer=1024,
                            input=True, input_device_index=int(pick["index"]), stream_callback=callback)
            self.status = "on"
            while not self._stop.is_set() and stream.is_active():
                time.sleep(0.1)
        finally:
            try:
                if stream is not None:
                    stream.stop_stream(); stream.close()
            finally:
                p.terminate()

    def _run_soundcard(self, device):
        sc: Any = optional("soundcard")
        speaker = next((s for s in sc.all_speakers() if device and device in s.name), None) or sc.default_speaker()
        mic = sc.get_microphone(id=str(speaker.name), include_loopback=True)
        self.rate, self.device_name = 48000, speaker.name
        with mic.recorder(samplerate=self.rate, channels=2) as rec:
            self.status = "on"
            while not self._stop.is_set():
                data = rec.record(numframes=1024)
                self.feed(data.mean(axis=1))


def spectrum_bands(samples, rate, bands=40, lo=40.0, hi=16000.0, floor_db=-78.0):
    """0..1 level per log-spaced band from the newest samples (Hann window FFT)."""
    n = len(samples)
    win = np.hanning(n)
    mag = np.abs(np.fft.rfft(samples * win)) / (n / 4.0)
    freqs = np.fft.rfftfreq(n, 1.0 / rate)
    edges = np.geomspace(lo, min(hi, rate / 2.0 - 1), bands + 1)
    out = np.zeros(bands, dtype="float32")
    for i in range(bands):
        sel = (freqs >= edges[i]) & (freqs < edges[i + 1])
        if sel.any():
            out[i] = mag[sel].max()
        else:                                           # narrow low bands between FFT bins: interpolate
            out[i] = np.interp((edges[i] + edges[i + 1]) / 2, freqs, mag)
    db = 20.0 * np.log10(np.maximum(out, 1e-9))
    return np.clip((db - floor_db) / -floor_db, 0.0, 1.0)


def scope_trace(samples, width=512):
    """A trigger-stabilised slice (rising zero crossing) resampled to `width` points in -1..1."""
    x = samples[-2048:]
    half = len(x) // 2
    seg = x[:half]
    cross = np.where((seg[:-1] < 0) & (seg[1:] >= 0))[0]
    start = int(cross[0]) if cross.size else 0
    window = x[start:start + half]
    if window.size < 8:
        window = x[:half]
    idx = np.linspace(0, window.size - 1, width)
    return np.interp(idx, np.arange(window.size), window)
