"""One build script for all platforms (Nuitka, standalone folder - what the installers / AppImage / .app wrap).

    python packaging/nuitka_build.py            ->  dist/KeyLabGrandOrgueBridge/ (run it, or wrap it with installer.iss / AppImage / dmg)
    python packaging/nuitka_build.py --onefile  ->  single file (slower start, more antivirus false positives: not for releases)

Requires:  pip install -r requirements.txt -r requirements-build.txt     (+ a C compiler: MSVC / MinGW on Windows, gcc on Linux, Xcode tools on macOS)
CHANGELOG
2.0.0  New (replaces the 1.0 hand-run command line).
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from version import APP_NAME, APP_VERSION  # noqa: E402

onefile = "--onefile" in sys.argv
args = [
    sys.executable, "-m", "nuitka",
    "--onefile" if onefile else "--standalone",
    "--enable-plugin=pyside6",
    "--assume-yes-for-downloads",
    "--output-dir=" + os.path.join(ROOT, "dist"),
    "--output-filename=KeyLabGrandOrgueBridge" + (".exe" if sys.platform == "win32" else ""),
    f"--product-name={APP_NAME}", f"--product-version={APP_VERSION}", f"--file-version={APP_VERSION}",
    "--company-name=MackyBMC",
    # the program imports its stave-editor modules by bare name: tell Nuitka about them
    "--include-package=keylab_bridge",
    *[f"--include-module={m}" for m in ("translations", "polish", "themes", "themes_ui", "lastdir", "go_midi_setup", "solfa",
                                        "core", "render", "engrave_job", "chrome", "roll_window", "track_panel", "quant_tools", "midi_stave", "sessionmeta", "stave_station")],
    "--include-package=music21", "--include-package-data=music21",
    "--include-package=verovio", "--include-package-data=verovio",
    "--include-package=qtawesome", "--include-package-data=qtawesome",
    "--include-package=mido", "--include-package=rtmidi",
    "--nofollow-import-to=pytest,tkinter,scipy,IPython",
    "--python-flag=no_site",
]
if sys.platform == "win32":
    args += ["--windows-console-mode=attach"]
    if os.path.exists(os.path.join(ROOT, "assets", "app.ico")):
        args += ["--windows-icon-from-ico=" + os.path.join(ROOT, "assets", "app.ico")]
elif sys.platform == "darwin":
    args += ["--macos-create-app-bundle", f"--macos-app-name={APP_NAME}", f"--macos-app-version={APP_VERSION}"]
    if os.path.exists(os.path.join(ROOT, "assets", "app.icns")):
        args += ["--macos-app-icon=" + os.path.join(ROOT, "assets", "app.icns")]
for name in ("config.yaml", "LICENSE", "THIRD_PARTY_NOTICES.md", "CHANGELOG.md"):
    if os.path.exists(os.path.join(ROOT, name)):
        args += [f"--include-data-files={os.path.join(ROOT, name)}={name}"]
args.append(os.path.join(ROOT, "keylab_go_bridge.py"))
print(" ".join(args))
sys.exit(subprocess.call(args, cwd=ROOT, env={**os.environ, "PYTHONPATH": os.pathsep.join([ROOT, os.path.join(ROOT, "midi_stave")])}))
