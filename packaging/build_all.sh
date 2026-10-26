#!/usr/bin/env bash
# Linux / macOS local build. Windows: see build_windows.ps1.  Output in dist/.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv-build && source .venv-build/bin/activate
pip install -U pip -r requirements.txt -r requirements-build.txt
python packaging/nuitka_build.py
case "$(uname)" in
  Linux)  # AppImage: needs appimagetool on PATH
          APPDIR=dist/AppDir; rm -rf "$APPDIR"; mkdir -p "$APPDIR/usr/bin"
          cp -r dist/keylab_go_bridge.dist/* "$APPDIR/usr/bin/"
          cp packaging/linux/keylab-bridge.desktop "$APPDIR/"; cp assets/app.png "$APPDIR/keylab-bridge.png" 2>/dev/null || true
          printf '#!/bin/sh\nexec "$(dirname "$0")/usr/bin/KeyLabGrandOrgueBridge" "$@"\n' > "$APPDIR/AppRun"; chmod +x "$APPDIR/AppRun"
          command -v appimagetool >/dev/null && ARCH=x86_64 appimagetool "$APPDIR" "dist/KeyLabGrandOrgueBridge-$(python -c 'from version import APP_VERSION as v;print(v)')-x86_64.AppImage" || echo "appimagetool not found: AppDir is in dist/AppDir" ;;
  Darwin) hdiutil create -volname "KeyLab GrandOrgue Bridge" -srcfolder dist/keylab_go_bridge.app -ov -format UDZO "dist/KeyLabGrandOrgueBridge-$(python -c 'from version import APP_VERSION as v;print(v)').dmg" ;;
esac
