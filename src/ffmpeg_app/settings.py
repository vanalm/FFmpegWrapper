from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from .options import PRESETS


SETTINGS_PATH = Path.home() / ".ffmpeg_app_settings.json"

DEFAULT_NOTES_PROMPT = (
    "You are a meeting notes assistant. Given a transcript of a meeting or "
    "recording, produce clear, well-organized meeting notes. Include: a brief "
    "summary, key discussion points, action items, and decisions made. Use "
    "bullet points and headers for readability."
)

PROVIDERS = ["openai", "gemini"]

MODELS_BY_PROVIDER: dict[str, list[str]] = {
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4.1-nano",
        "gpt-5.2",
        "o3",
        "o4-mini",
    ],
    "gemini": [
        "gemini-2.0-flash",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
    ],
}


@dataclass
class AppSettings:
    # ffmpeg defaults
    include_audio: bool = True
    crf: int = 23
    speed: int = 1
    fps: Optional[int] = None
    preset: str = "fast"
    default_suffix: str = "processed"
    ffmpeg_path: Optional[str] = None

    # AI feature toggles (remembered defaults)
    transcript_enabled: bool = False
    notes_enabled: bool = False

    # API keys
    deepgram_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None

    # Notes provider / model
    notes_provider: str = "openai"
    notes_model: str = "gpt-4o"
    notes_system_prompt: str = field(default=DEFAULT_NOTES_PROMPT)

    @classmethod
    def load(cls, path: Path = SETTINGS_PATH) -> "AppSettings":
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text())
            preset = data.get("preset", "fast")
            if preset not in PRESETS:
                preset = "fast"
            provider = data.get("notes_provider", "openai")
            if provider not in PROVIDERS:
                provider = "openai"
            model = data.get("notes_model", "gpt-4o") or "gpt-4o"
            return cls(
                include_audio=bool(data.get("include_audio", True)),
                crf=int(data.get("crf", 23)),
                speed=int(data.get("speed", 1)),
                fps=int(data["fps"]) if data.get("fps") not in (None, "") else None,
                preset=preset,
                default_suffix=str(data.get("default_suffix", "processed")),
                ffmpeg_path=data.get("ffmpeg_path") or None,
                transcript_enabled=bool(data.get("transcript_enabled", False)),
                notes_enabled=bool(data.get("notes_enabled", False)),
                deepgram_api_key=data.get("deepgram_api_key") or None,
                openai_api_key=data.get("openai_api_key") or None,
                gemini_api_key=data.get("gemini_api_key") or None,
                notes_provider=provider,
                notes_model=model,
                notes_system_prompt=str(
                    data.get("notes_system_prompt", DEFAULT_NOTES_PROMPT)
                ),
            )
        except Exception:
            return cls()

    def save(self, path: Path = SETTINGS_PATH) -> None:
        path.write_text(json.dumps(asdict(self), indent=2))

