import os
import sys
from pathlib import Path


def main() -> None:
    project_src = Path(__file__).parent / "src"
    sys.path.insert(0, str(project_src))
    os.environ.setdefault("PYTHONPATH", str(project_src))
    from ffmpeg_app.main import main as run_app  # type: ignore

    run_app()


if __name__ == "__main__":
    main()

