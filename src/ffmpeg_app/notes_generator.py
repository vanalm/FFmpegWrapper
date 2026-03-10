from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from openai import OpenAI

LogCallback = Callable[[str], None]


def generate_notes(
    transcript: str,
    system_prompt: str,
    api_key: str,
    model: str = "gpt-4o",
    log: Optional[LogCallback] = None,
) -> str:
    if log:
        log(f"Generating meeting notes with {model}...\n")

    client = OpenAI(api_key=api_key)

    response = client.responses.create(
        model=model,
        instructions=system_prompt,
        input=transcript,
    )

    notes = response.output_text
    if log:
        log(f"Notes generated ({len(notes)} chars)\n")
    return notes


def run_notes_generation(
    transcript: str,
    input_path: Path,
    output_dir: Path,
    system_prompt: str,
    api_key: str,
    model: str = "gpt-4o",
    log: Optional[LogCallback] = None,
) -> Path:
    """Generate meeting notes from transcript and save to file.

    Returns the path to the notes file.
    """
    notes = generate_notes(
        transcript,
        system_prompt=system_prompt,
        api_key=api_key,
        model=model,
        log=log,
    )

    notes_path = output_dir / f"{input_path.stem}_notes.txt"
    notes_path.write_text(notes, encoding="utf-8")
    if log:
        log(f"Notes saved to {notes_path}\n")
    return notes_path
