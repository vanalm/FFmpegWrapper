from pathlib import Path

from ffmpeg_app.ffmpeg_runner import FFmpegRunner
from ffmpeg_app.options import FFmpegOptions


def test_runner_builds_command_with_custom_path(monkeypatch):
    runner = FFmpegRunner()
    runner.set_ffmpeg_binary("/custom/ffmpeg")
    opts = FFmpegOptions(input_path=Path("/tmp/in.mp4"), output_path=Path("/tmp/out.mp4"))
    cmd = runner.build_command(opts)
    assert cmd[0] == "/custom/ffmpeg"

