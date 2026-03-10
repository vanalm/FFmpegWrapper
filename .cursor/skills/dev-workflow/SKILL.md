---
name: dev-workflow
description: Development workflow for the FFmpegWrapper PySide6 desktop app. Use when running the app locally, running tests, adding features, modifying the UI, changing settings, updating dependencies, or working with the transcription/notes pipeline.
---

# FFmpegWrapper Development Workflow

## Run Locally

```bash
cd /Users/jacobvanalmelo/code/ffmpeg_app
PYTHONPATH=src python -m ffmpeg_app.main
```

No build step needed -- this launches the PySide6 GUI directly.

## Run Tests

```bash
cd /Users/jacobvanalmelo/code/ffmpeg_app
PYTHONPATH=src python -m pytest tests/ -v
```

Tests live in `tests/` and cover `options.py`, `settings.py`, and `ffmpeg_runner.py`.

## Install Dependencies

```bash
pip install -r requirements.txt        # runtime
pip install -e ".[dev]"                 # runtime + pytest
```

Runtime deps: `PySide6>=6.6,<7.0`, `openai>=1.60`. Dev: `pytest>=8.0`.

## Architecture

```
src/ffmpeg_app/
├── main.py            # Entry: calls ui.launch()
├── ui.py              # PySide6 GUI: MainWindow, SettingsDialog, workers
├── settings.py        # AppSettings dataclass, JSON persistence
├── options.py         # FFmpegOptions dataclass, arg builder, output path
├── ffmpeg_runner.py   # Subprocess runner with cancel support
├── transcriber.py     # Audio extraction + Deepgram STT
└── notes_generator.py # OpenAI Responses API for meeting notes
```

### Data Flow

1. User selects input video, adjusts options in GUI
2. `FFmpegOptions.to_args()` builds the ffmpeg command
3. `FFmpegRunner.run()` executes in `FFmpegWorker` on a `QThread`
4. If transcript/notes toggles are on, `PostProcessWorker` chains after ffmpeg:
   - `transcriber.run_transcription()` extracts audio, calls Deepgram
   - `notes_generator.run_notes_generation()` sends transcript to OpenAI

### Settings

- Persisted to `~/.ffmpeg_app_settings.json`
- `AppSettings` dataclass with `load()`/`save()` class methods
- Fields: ffmpeg defaults, API keys (Deepgram, OpenAI, Gemini), notes provider/model/prompt

### Adding a New Setting

1. Add field to `AppSettings` in `settings.py` with a default value
2. Add parsing in `AppSettings.load()` with `data.get("field", default)`
3. Add widget in `SettingsDialog._build_ui()` in `ui.py`
4. Include in `SettingsDialog._save()` result construction
5. If it affects the main window, update `_apply_settings_to_controls()`

### Adding a New Main Window Control

1. Create the widget in `MainWindow._build_ui()`
2. Wire signals in `MainWindow._wire_signals()`
3. Read the value in `_start_run()` when building options
4. If it affects output path, connect to `_refresh_output_path()`

### Modifying the Transcription Pipeline

- `transcriber.py` uses `urllib.request` (stdlib) to call Deepgram REST API
- Audio extracted to temp WAV via ffmpeg subprocess
- Deepgram endpoint: `https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&paragraphs=true`

### Modifying the Notes Pipeline

- `notes_generator.py` uses the `openai` SDK (`client.responses.create()`)
- System prompt and model are configurable in settings
- Provider field exists for future Gemini support (not yet implemented)

## Key Conventions

- All source under `src/ffmpeg_app/`, tests under `tests/`
- Entry point for PyInstaller: `app_entry.py` (adds `src` to path)
- Entry point for dev: `python -m ffmpeg_app.main` with `PYTHONPATH=src`
- GUI built with manual PySide6 layouts (no QML, no Designer files)
- Background work uses `QThread` + `QObject.moveToThread()` pattern
- Settings dialog returns `result_settings` on accept; caller saves
