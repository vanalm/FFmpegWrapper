from pathlib import Path

from ffmpeg_app.options import FFmpegOptions, suggest_output_path


def test_suggest_output_path_defaults():
    input_path = Path("/tmp/video.mov")
    opts = FFmpegOptions(include_audio=True, crf=23, speed=1, preset="fast")
    out = suggest_output_path(input_path, opts)
    assert out.name == "video_processed.mp4"


def test_suggest_output_path_suffixes():
    input_path = Path("/tmp/video.mov")
    opts = FFmpegOptions(include_audio=False, crf=28, speed=2, fps=30, preset="slow")
    out = suggest_output_path(input_path, opts, default_suffix="custom")
    # components should be present
    name = out.name
    assert "muted" in name
    assert "2x" in name
    assert "crf28" in name
    assert "30fps" in name
    assert "slow" in name
    assert name.endswith(".mp4")


def test_build_args_respects_options():
    input_path = Path("/tmp/video.mov")
    opts = FFmpegOptions(
        input_path=input_path,
        include_audio=False,
        crf=30,
        speed=3,
        fps=24,
        preset="fast",
        output_path=Path("/tmp/out.mp4"),
    )
    args = opts.to_args()
    joined = " ".join(args)
    assert "-an" in args
    assert "-crf 30" in joined
    assert "setpts=0.3333" in joined
    assert "fps=24" in joined
    assert args[-1] == "/tmp/out.mp4"

