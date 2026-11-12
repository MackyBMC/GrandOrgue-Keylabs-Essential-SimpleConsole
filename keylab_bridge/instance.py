"""Is the bridge (or GrandOrgue) already running?

CHANGELOG
2026-11-12  New. acquire_lock(): one bridge per config folder (file lock, released by the OS when the process dies, so a crash never leaves it stuck).
            process_running(): is GrandOrgue (or any program) running right now.
"""
import os
import subprocess
import sys
import tempfile

_held = []                                  # the open lock file lives as long as the process


def acquire_lock(config_path):
    """True when this process now owns the bridge lock; False when another bridge already runs."""
    folder = os.path.dirname(os.path.abspath(config_path)) if config_path else tempfile.gettempdir()
    for path in (os.path.join(folder, "bridge.lock"), os.path.join(tempfile.gettempdir(), "keylab_bridge.lock")):
        try:
            handle = open(path, "a+")
        except OSError:
            continue
        try:
            if sys.platform == "win32":
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        _held.append(handle)
        return True
    return True                             # no writable place for a lock: do not block the user


def process_running(*names):
    """True when a process with one of these image names (GrandOrgue.exe / GrandOrgue) is running. Unknown -> False."""
    try:
        if sys.platform == "win32":
            for name in names:
                out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {name}", "/NH", "/FO", "CSV"], capture_output=True, text=True,
                                     timeout=6, creationflags=0x08000000).stdout
                if name.lower() in out.lower():
                    return True
            return False
        for name in names:
            if subprocess.run(["pgrep", "-ix", name.replace(".exe", "")], capture_output=True, timeout=6).returncode == 0:
                return True
    except (OSError, subprocess.SubprocessError):
        pass
    return False


def grandorgue_running():
    return process_running("GrandOrgue.exe", "GrandOrgue", "grandorgue")
