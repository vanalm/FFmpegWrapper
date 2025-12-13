from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from .options import PRESETS


SETTINGS_PATH = Path.home() / ".ffmpeg_app_settings.json"


@dataclass
class AppSettings:
    include_audio: bool = True
    crf: int = 23
    speed: int = 1
    fps: Optional[int] = None
    preset: str = "fast"
    default_suffix: str = "processed"
    ffmpeg_path: Optional[str] = None  # use PATH when None

    @classmethod
    def load(cls, path: Path = SETTINGS_PATH) -> "AppSettings":
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text())
            preset = data.get("preset", "fast")
            if preset not in PRESETS:
                preset = "fast"
            return cls(
                include_audio=bool(data.get("include_audio", True)),
                crf=int(data.get("crf", 23)),
                speed=int(data.get("speed", 1)),
                fps=int(data["fps"]) if data.get("fps") not in (None, "") else None,
                preset=preset,
                default_suffix=str(data.get("default_suffix", "processed")),
                ffmpeg_path=data.get("ffmpeg_path") or None,
            )
        except Exception:
            return cls()

    def save(self, path: Path = SETTINGS_PATH) -> None:
        path.write_text(json.dumps(asdict(self), indent=2))

