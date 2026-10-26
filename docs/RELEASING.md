# Releasing

1. Bump `APP_VERSION` in `version.py`; the app, executable metadata, and installer version are derived from it.
2. Add the entry to `CHANGELOG.md` and build/test the Windows installer.
3. Local Windows test: `powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1`
   - run `dist\keylab_go_bridge.dist\KeyLabGrandOrgueBridge.exe` (check GrandOrgue opens the configured organ, existing setter combinations appear, Stave Station opens, and engraving works),
   - run the installer from `dist\installer\`, then uninstall and confirm user data in `%APPDATA%\KeyLabGrandOrgue` survives.
4. Portable test: copy the dist folder, add an empty `portable.flag` next to the exe; settings must then be written beside the exe.
5. After the build is confirmed, tag and push `v<APP_VERSION>` (for example, `git tag v2.0.1 && git push origin v2.0.1`) - the workflow builds Windows (stable) and Linux/macOS (experimental), writes `SHA256SUMS`, and publishes the release.
6. Antivirus false positives: Nuitka builds are rare offenders but unsigned exes can be flagged. Publish the SHA256SUMS; consider a code-signing certificate (e.g. SignPath for open source) later.
7. Linux/macOS: workflow jobs are `continue-on-error`; promote them to stable only after someone has tested the AppImage / dmg on a real machine.
