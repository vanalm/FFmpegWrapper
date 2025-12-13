from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

PRESETS = [
    "ultrafast",
    "superfast",
    "veryfast",
    "faster",
    "fast",
    "medium",
    "slow",
]


@dataclass
class FFmpegOptions:
    input_path: Optional[Path] = None
    output_path: Optional[Path] = None
    include_audio: bool = True
    crf: int = 23  # lower is better quality, 18–35 typical
    speed: int = 1  # playback speed multiplier (1–20)
    fps: Optional[int] = None  # None -> keep original
    preset: str = "fast"

    def to_args(self) -> List[str]:
        if not self.input_path:
            raise ValueError("Input path is required.")
        output = self.output_path or suggest_output_path(self.input_path, self)

        args: List[str] = ["-i", str(self.input_path)]
        if not self.include_audio:
            args.append("-an")

        vf_filters = []
        if self.speed != 1:
            vf_filters.append(f"setpts={1/self.speed:.4f}*PTS")
        if self.fps:
            vf_filters.append(f"fps={self.fps}")
        if vf_filters:
            args.extend(["-filter:v", ",".join(vf_filters)])

        args.extend(
            [
                "-c:v",
                "libx264",
                "-crf",
                str(self.crf),
                "-preset",
                self.preset,
                "-movflags",
                "+faststart",
            ]
        )

        if self.include_audio:
            args.extend(["-c:a", "aac"])

        args.append(str(output))
        return args


def suggest_output_path(
    input_path: Path, options: FFmpegOptions, default_suffix: str = "processed"
) -> Path:
    base = input_path.with_suffix("")
    suffix_parts = []
    if not options.include_audio:
        suffix_parts.append("muted")
    if options.speed != 1:
        suffix_parts.append(f"{options.speed}x")
    if options.crf != 23:
        suffix_parts.append(f"crf{options.crf}")
    if options.fps:
        suffix_parts.append(f"{options.fps}fps")
    if options.preset != "fast":
        suffix_parts.append(options.preset)

    suffix = "_".join(suffix_parts) if suffix_parts else default_suffix
    new_ext = ".mp4" if input_path.suffix.lower() != ".mp4" else input_path.suffix
    return Path(f"{base}_{suffix}{new_ext}")
