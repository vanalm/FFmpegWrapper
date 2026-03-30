# FFmpegWrapper

A minimal macOS desktop app (PySide6) for post-processing screen recordings and audio files. Wraps common `ffmpeg` options behind toggles and sliders, and optionally transcribes audio via Deepgram and generates meeting notes via OpenAI.

## Features

- **Drag & drop** or browse for video (`.mp4`, `.mov`, `.mkv`, `.avi`, `.webm`) or audio (`.mp3`, `.wav`, `.m4a`, `.aac`, `.flac`, `.ogg`, `.opus`, `.wma`) files
- Auto-derived, editable output path with options-aware suffix
- **Compress** — re-encode video with H.264 (CRF, speed, FPS, preset controls); re-encode audio files to AAC
- **Get Transcript** — extract audio and transcribe via Deepgram (speaker-diarized, timestamped)
- **Get Notes** — generate structured meeting notes from the transcript via OpenAI (or Gemini)
- Video-specific controls auto-disable when an audio file is loaded
- Settings dialog (⚙) for defaults, custom `ffmpeg` path, and API keys
- Settings persist to `~/.ffmpeg_app_settings.json`

## Quick start

```bash
git clone <repo>
cd ffmpeg_app
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
PYTHONPATH=src python -m ffmpeg_app.main
```

No build step — this launches the GUI directly.

## ffmpeg

The app uses the `ffmpeg` binary on your `PATH`. It is **not bundled**.

| Platform | Install |
|----------|---------|
| macOS | `brew install ffmpeg` |
| Ubuntu/Debian | `sudo apt install ffmpeg` |
| Windows | Download from [ffmpeg.org](https://ffmpeg.org/download.html), add to PATH |

If `ffmpeg` is in a non-standard location, set a custom path in Settings (⚙ → Custom ffmpeg path).

## API keys (optional)

Keys are entered in Settings (⚙) and never committed to the repo.

| Feature | Key needed | Get one at |
|---------|-----------|------------|
| Get Transcript | Deepgram | [console.deepgram.com](https://console.deepgram.com) |
| Get Notes | OpenAI (or Gemini) | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |

Compress works with no keys at all.

## Controls

| Control | Effect |
|---------|--------|
| Compression (CRF) | 15–35; lower = higher quality (video only) |
| Speed | 1–20× playback speed via `setpts` (video only) |
| FPS | 0 keeps source FPS; otherwise applies `fps` filter (video only) |
| Preset | H.264 encode speed/size trade-off (video only) |
| Include audio | Strip audio track with `-an` when unchecked (video only) |
| Output path | Auto-filled with options-aware suffix; fully editable |

Video-only controls are greyed out when an audio file is loaded.

## Tests

```bash
PYTHONPATH=src python -m pytest tests/ -v
```

No API keys required to run tests.

## Building a macOS .app bundle

```bash
pip install pyinstaller
pyinstaller --clean -y pyinstaller-macos.spec
# Output: dist/FFmpegWrapper.app
```

For code-signing and notarization, see the [build-sign-notarize skill](.cursor/skills/build-sign-notarize/SKILL.md).

## Project layout

```
src/ffmpeg_app/
├── main.py            # Entry point
├── ui.py              # PySide6 GUI, workers
├── settings.py        # AppSettings dataclass, JSON persistence
├── options.py         # FFmpegOptions, arg builder, output path
├── ffmpeg_runner.py   # Subprocess runner with cancel
├── transcriber.py     # Audio extraction + Deepgram API
└── notes_generator.py # OpenAI / Gemini notes generation
```
