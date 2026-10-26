"""Where things live. Program files are read-only (Program Files / .app / AppImage); everything the user changes goes to the
per-user data folder, so an installed copy, a portable copy and a source checkout all behave the same.

    Windows  %APPDATA%\\KeyLabGrandOrgue        Linux  ~/.config/KeyLabGrandOrgue        macOS  ~/Library/Application Support/KeyLabGrandOrgue
Portable mode: an empty file called `portable.flag` next to the program keeps config.yaml, takes etc. beside it instead.

CHANGELOG
2.0.0  New.
"""
import os
import sys

APP_ID = "KeyLabGrandOrgue"


def app_dir():
    """Folder of the running program (the .exe / the script)."""
    if getattr(sys, "frozen", False) or "__compiled__" in globals():
        return os.path.dirname(os.path.abspath(sys.argv[0] if "__compiled__" in globals() else sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def is_portable():
    return os.path.exists(os.path.join(app_dir(), "portable.flag"))


def _writable(folder):
    try:
        probe = os.path.join(folder, ".write_test")
        with open(probe, "w"):
            pass
        os.remove(probe)
        return True
    except OSError:
        return False


def user_data_dir():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    path = os.path.join(base, APP_ID)
    os.makedirs(path, exist_ok=True)
    return path


def data_dir():
    """Config, window layout, takes, generated GrandOrgue import files."""
    here = app_dir()
    if is_portable() or (not getattr(sys, "frozen", False) and "__compiled__" not in globals() and _writable(here)):
        return here                                       # portable copy, or running from source: stay beside the scripts
    return user_data_dir()


def first_run_config(default_name="config.yaml"):
    """Installed copy: put the shipped default config in the user folder once, return its path."""
    target = os.path.join(data_dir(), default_name)
    shipped = os.path.join(app_dir(), default_name)
    if not os.path.exists(target) and os.path.exists(shipped) and os.path.abspath(shipped) != os.path.abspath(target):
        import shutil
        shutil.copyfile(shipped, target)
    return target
