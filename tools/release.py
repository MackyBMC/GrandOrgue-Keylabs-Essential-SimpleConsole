"""Release in one step: bump version.py, stamp CHANGELOG.md, commit, push the branch, tag v<version>, push the tag (the GitHub workflow then builds and publishes).

Usage: python tools/release.py 2.0.9 [--dry-run]
Stops (nothing changed) when the tag exists, the version is not X.Y.Z, or the branch is not release-2.0. Never touches v1 tags.

CHANGELOG
2026-11-15  New.
"""
import datetime
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRANCH = "release-2.0"


def git(*args: str, check: bool = True) -> str:
    done = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if check and done.returncode:
        sys.exit(f"git {' '.join(args)} failed:\n{done.stderr.strip() or done.stdout.strip()}")
    return done.stdout.strip()


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    version = args[0].lstrip("v") if args else ""
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        sys.exit("Give the version as X.Y.Z, e.g. 2.0.9")
    if version.startswith("1."):
        sys.exit("v1 is left alone.")
    tag = "v" + version
    if git("branch", "--show-current") != BRANCH:
        sys.exit(f"Switch to {BRANCH} first.")
    if git("tag", "--list", tag):
        sys.exit(f"Tag {tag} already exists.")
    today = datetime.date.today().isoformat()
    vp, cp = ROOT / "version.py", ROOT / "CHANGELOG.md"
    text = vp.read_text(encoding="utf-8")
    new = re.sub(r'APP_VERSION = "[^"]*"', f'APP_VERSION = "{version}"', text, count=1)
    new = new.replace("CHANGELOG\n", f"CHANGELOG\n{today}  Prepare release {tag}.\n", 1)
    log = cp.read_text(encoding="utf-8")
    log = re.sub(r"^## \d+\.\d+\.\d+ \(unreleased\)[^\n]*", f"## {version} ({today})", log, count=1, flags=re.M)
    log = log.replace("\n## Unreleased\n", f"\n## {version} ({today})\n", 1) if f"## {version}" not in log else log
    print(f"{'DRY RUN: ' if dry else ''}release {tag} on {BRANCH}")
    if dry:
        return
    vp.write_text(new, encoding="utf-8")
    cp.write_text(log, encoding="utf-8")
    git("add", "-A")
    git("commit", "-m", f"Release {tag}")
    git("push", "origin", BRANCH)
    git("tag", tag)
    git("push", "origin", tag)
    print(f"Pushed {tag}. Watch the Actions tab; the Release appears when the build is green.")


if __name__ == "__main__":
    main()
