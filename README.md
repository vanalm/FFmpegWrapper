# FFmpeg Desktop Wrapper (Python/PySide6)

A minimal cross-platform desktop app (macOS, Linux, Windows) that wraps common `ffmpeg` options for screen-capture post-processing with toggles and sliders:

- File input (browse or drag/drop)
- Auto-derived, editable output path with sensible suffix
- Audio on/off
- Compression (CRF) slider
- Speed slider (1–20x)
- Optional FPS override
- H.264 preset selector
- Run/Cancel with live log
- Gear/settings to set defaults (audio, CRF, speed, fps, preset, suffix, custom ffmpeg path)

Uses the `ffmpeg` binary available on your `PATH` (not bundled).

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
PYTHONPATH=src python -m ffmpeg_app.main   # Windows: set PYTHONPATH=src && python -m ffmpeg_app.main
```

### Settings / defaults
- Click the gear button to set defaults: audio, CRF, speed, fps, preset, default output suffix, and optional custom `ffmpeg` path (falls back to PATH when blank).
- Settings persist to `~/.ffmpeg_app_settings.json`.

### Tests
```bash
pip install -e .[dev]
PYTHONPATH=src pytest
```

## ffmpeg installation

- macOS: `brew install ffmpeg`
- Linux: use your package manager, e.g. `sudo apt-get install ffmpeg`
- Windows: install from https://www.gyan.dev/ffmpeg/builds/ and add `ffmpeg.exe` to PATH

## Controls at a glance

- Audio toggle: include or strip audio (`-an` when off).
- Compression (CRF): 15–35 (lower = higher quality).
- Speed: 1–20x via `setpts`.
- FPS: 0 keeps source; otherwise uses `fps` filter.
- Preset: H.264 preset for encode speed/size trade-off.
- Output path: auto-filled from input with suffix based on options; editable.

## Example equivalent CLI

An example command similar to the UI defaults might be:

```bash
ffmpeg -i input.mov -filter:v "setpts=0.5*PTS,fps=30" -c:v libx264 -crf 23 -preset fast -movflags +faststart -c:a aac output_processed.mp4
```

## Building / bundling (optional)

The app runs directly with Python. For a macOS `.app` bundle using the placeholder gear icon:

```bash
pip install pyinstaller
pyinstaller --clean pyinstaller-macos.spec
# Bundle will be at dist/FFmpegWrapper.app
```

`ffmpeg` still needs to be reachable (custom path from settings is supported).

