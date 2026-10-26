"""Locate and start GrandOrgue for the graphical bridge."""

import os
import shutil
import subprocess
import sys


def find_grandorgue():
    names = ("GrandOrgue.exe", "GrandOrgue") if sys.platform == "win32" else ("GrandOrgue", "grandorgue")
    for name in names:
        executable = shutil.which(name)
        if executable:
            return executable

    if sys.platform == "win32":
        roots = (
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
            os.environ.get("ProgramW6432"),
        )
        relative_paths = (
            os.path.join("GrandOrgue", "bin", "GrandOrgue.exe"),
            os.path.join("GrandOrgue", "GrandOrgue.exe"),
        )
        for root in dict.fromkeys(path for path in roots if path):
            for relative_path in relative_paths:
                candidate = os.path.join(root, relative_path)
                if os.path.isfile(candidate):
                    return candidate
    elif sys.platform == "darwin":
        candidate = "/Applications/GrandOrgue.app/Contents/MacOS/GrandOrgue"
        if os.path.isfile(candidate):
            return candidate

    return None


def start_grandorgue(organ_path=""):
    executable = find_grandorgue()
    if not executable:
        raise FileNotFoundError("GrandOrgue executable was not found")

    command = [executable]
    warning = None
    if organ_path:
        if os.path.isfile(organ_path):
            command.append(organ_path)
        else:
            warning = f"Configured GrandOrgue organ file was not found: {organ_path}"

    subprocess.Popen(command, close_fds=True)
    return warning
