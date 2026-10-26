# Releasing

1. Bump `APP_VERSION` in `version.py`; the app, executable metadata, and installer version are derived from it.
2. Add the entry to `CHANGELOG.md` and update the bridge README/changelog as appropriate.
3. Local Windows test: `powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1`
   - run `dist\keylab_go_bridge.dist\KeyLabGrandOrgueBridge.exe` (check GrandOrgue opens the configured organ, existing setter combinations appear, Stave Station opens, and engraving works),
   - run the installer from `dist\installer\`, then uninstall and confirm user data in `%APPDATA%\KeyLabGrandOrgue` survives.
4. Portable test: copy the dist folder, add an empty `portable.flag` next to the exe; settings must then be written beside the exe.
5. After validation, tag and push `v<APP_VERSION>` to build all platform jobs. For a Linux-only experimental prerelease, use a tag in the form `v<APP_VERSION>-linux.1` (for example, `v2.0.2-linux.1`); this builds only Linux and publishes the release as a prerelease. The stable Windows release is unchanged.
6. Antivirus false positives: Nuitka builds are rare offenders but unsigned exes can be flagged. Publish the SHA256SUMS; consider a code-signing certificate (e.g. SignPath for open source) later.
7. Linux/macOS: Linux prereleases and macOS builds are experimental; macOS remains deferred. Promote either platform to stable only after testing it on a real machine.
