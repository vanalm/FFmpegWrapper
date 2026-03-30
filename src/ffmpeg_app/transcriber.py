from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Callable, Optional

LogCallback = Callable[[str], None]


def _find_ffmpeg(ffmpeg_binary: Optional[str] = None) -> str:
    binary = ffmpeg_binary or "ffmpeg"
    if shutil.which(binary) is None:
        raise FileNotFoundError(f"ffmpeg not found: {binary}")
    return binary


def extract_audio(
    input_path: Path,
    output_path: Path,
    ffmpeg_binary: Optional[str] = None,
    log: Optional[LogCallback] = None,
) -> None:
    binary = _find_ffmpeg(ffmpeg_binary)
    cmd = [
        binary,
        "-i", str(input_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        "-y",
        str(output_path),
    ]
    if log:
        log(f"Extracting audio: {' '.join(cmd)}\n")
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"Audio extraction failed:\n{proc.stderr}")


def _fmt_ts(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def transcribe_deepgram(
    audio_path: Path,
    api_key: str,
    log: Optional[LogCallback] = None,
) -> str:
    if log:
        log("Sending audio to Deepgram...\n")

    audio_data = audio_path.read_bytes()
    url = (
        "https://api.deepgram.com/v1/listen"
        "?model=nova-2&smart_format=true&paragraphs=true"
        "&diarize=true&utterances=true"
    )

    req = urllib.request.Request(
        url,
        data=audio_data,
        headers={
            "Authorization": f"Token {api_key}",
            "Content-Type": "audio/wav",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=300) as resp:
        body = json.loads(resp.read().decode())

    utterances = body.get("results", {}).get("utterances", [])
    if utterances:
        lines: list[str] = []
        for utt in utterances:
            speaker = utt.get("speaker", "?")
            start = _fmt_ts(utt.get("start", 0))
            end = _fmt_ts(utt.get("end", 0))
            text = utt.get("transcript", "")
            lines.append(f"[{start} - {end}] Speaker {speaker}: {text}")
        transcript = "\n\n".join(lines)
    else:
        channels = body.get("results", {}).get("channels", [])
        if not channels:
            raise RuntimeError("Deepgram returned no transcript data")
        transcript = (
            channels[0].get("alternatives", [{}])[0].get("transcript", "")
        )

    if log:
        log(f"Transcript received ({len(transcript)} chars)\n")
    return transcript


def run_transcription(
    input_path: Path,
    output_dir: Path,
    api_key: str,
    ffmpeg_binary: Optional[str] = None,
    log: Optional[LogCallback] = None,
) -> tuple[str, Path]:
    """Extract audio, transcribe via Deepgram, and save the transcript file.

    Returns (transcript_text, transcript_file_path).
    """
    with tempfile.TemporaryDirectory() as tmp:
        wav_path = Path(tmp) / "audio.wav"
        extract_audio(input_path, wav_path, ffmpeg_binary=ffmpeg_binary, log=log)
        transcript = transcribe_deepgram(wav_path, api_key, log=log)

    transcript_path = output_dir / f"{input_path.stem}_transcript.txt"
    transcript_path.write_text(transcript, encoding="utf-8")
    if log:
        log(f"Transcript saved to {transcript_path}\n")
    return transcript, transcript_path
