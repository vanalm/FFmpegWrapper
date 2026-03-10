---
name: build-sign-notarize
description: Build, code-sign, notarize, and package the FFmpegWrapper desktop app for distribution. Use when the user asks to build the app, create a release, sign the binary, notarize with Apple, package for distribution, or create installers for macOS/Windows/Linux.
---

# Build, Sign, and Notarize FFmpegWrapper

## Project Layout

```
ffmpeg_app/
├── app_entry.py                 # PyInstaller entry point
├── pyinstaller-macos.spec       # macOS bundle spec
├── entitlements.plist            # Hardened runtime entitlements (network access)
├── resources/app_icon.icns       # macOS app icon
├── src/ffmpeg_app/               # Application source
├── requirements.txt              # Runtime deps: PySide6, openai
└── pyproject.toml                # Project metadata and deps
```

## macOS Build + Sign + Notarize

### Prerequisites

- Python 3.9+ with `pyinstaller` and project deps installed
- `Developer ID Application` certificate in Keychain
- Notarization credentials stored as a keychain profile
- Local config file `signing-config.local.sh` at the repo root (gitignored)

### Signing Identity

Before signing, read `signing-config.local.sh` to get `CODESIGN_IDENTITY` and `NOTARIZE_PROFILE`. If the file is missing, run `security find-identity -v -p codesigning` to find the Developer ID Application hash and ask the user for their notarization keychain profile name.

If there are duplicate certs with the same name, use the SHA-1 hash (from the config file) to disambiguate.

### Full Pipeline

```bash
# 0. Load local signing config
source signing-config.local.sh

# 1. Clean and build
rm -rf dist/ build/
pyinstaller --clean -y pyinstaller-macos.spec

# 2. Sign with hardened runtime
cd dist
codesign --deep --force --options runtime \
  --entitlements ../entitlements.plist \
  --sign "$CODESIGN_IDENTITY" \
  FFmpegWrapper.app

# 3. Verify signature
codesign --verify --deep --strict FFmpegWrapper.app

# 4. Zip for notarization
rm -f FFmpegWrapper.zip
ditto -c -k --keepParent FFmpegWrapper.app FFmpegWrapper.zip

# 5. Submit for notarization (takes 1-3 min)
xcrun notarytool submit FFmpegWrapper.zip \
  --keychain-profile "$NOTARIZE_PROFILE" --wait

# 6. Staple the ticket
xcrun stapler staple FFmpegWrapper.app

# 7. Verify Gatekeeper
spctl -a -vv FFmpegWrapper.app
```

Expected final output: `FFmpegWrapper.app: accepted, source=Notarized Developer ID`

### Re-zip After Stapling

The zip from step 4 was created before stapling. If distributing a zip, re-create it:

```bash
cd dist
rm -f FFmpegWrapper.zip
ditto -c -k --keepParent FFmpegWrapper.app FFmpegWrapper.zip
```

### Troubleshooting

- **"ambiguous" signing error**: Use the SHA-1 hash from `signing-config.local.sh` instead of the name string.
- **Notarization rejected**: Run `xcrun notarytool log <submission-id> --keychain-profile "$NOTARIZE_PROFILE"` to see the rejection details.
- **Missing modules at runtime**: Add to `hiddenimports` in `pyinstaller-macos.spec`. Current list includes `openai`, `httpx`, `pydantic`, and their transitive deps.
- **Output dir not empty**: Use `-y` flag or `rm -rf dist/ build/` before building.
- **PyInstaller onefile deprecation warning**: Harmless for now; the spec produces a `.app` bundle correctly. Will need migration to onedir in PyInstaller v7.

### Entitlements

`entitlements.plist` grants:
- `com.apple.security.cs.allow-unsigned-executable-memory` -- required by Python/PyInstaller
- `com.apple.security.network.client` -- required for Deepgram and OpenAI API calls

If new entitlements are needed (e.g., camera, microphone), add them to `entitlements.plist` before signing.

## Windows Build (Not Yet Configured)

When adding Windows support:

1. Create `pyinstaller-windows.spec` based on the macOS spec
2. Replace `.icns` icon with `.ico` in the spec
3. Remove the `BUNDLE` section (Windows uses the EXE directly)
4. Sign with `signtool` if a code signing certificate is available
5. Consider packaging with NSIS or Inno Setup for an installer

## Linux Build (Not Yet Configured)

When adding Linux support:

1. Create `pyinstaller-linux.spec` based on the macOS spec
2. Remove the `BUNDLE` section and icon references
3. The output is a standalone binary at `dist/FFmpegWrapper`
4. Package as `.deb` with `dpkg-deb` or `.AppImage` with `appimagetool`
5. No code signing required for most distributions
