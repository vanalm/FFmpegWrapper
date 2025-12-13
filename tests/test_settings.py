from pathlib import Path

from ffmpeg_app.settings import AppSettings


def test_settings_round_trip(tmp_path: Path):
    settings_path = tmp_path / "settings.json"
    settings = AppSettings(
        include_audio=False,
        crf=30,
        speed=2,
        fps=60,
        preset="slow",
        default_suffix="demo",
        ffmpeg_path="/usr/local/bin/ffmpeg",
    )
    settings.save(settings_path)
    loaded = AppSettings.load(settings_path)
    assert loaded == settings

