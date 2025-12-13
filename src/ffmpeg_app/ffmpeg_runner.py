from __future__ import annotations

import shutil
import subprocess

from typing import Callable, Optional

from .options import FFmpegOptions

LogCallback = Callable[[str], None]
FinishCallback = Callable[[bool, Optional[str]], None]


class FFmpegRunner:
    """Build and run ffmpeg commands."""

    def __init__(self, ffmpeg_binary: str = "ffmpeg") -> None:
        self.ffmpeg_binary = ffmpeg_binary
        self._process: Optional[subprocess.Popen[str]] = None

    def set_ffmpeg_binary(self, path: Optional[str]) -> None:
        self.ffmpeg_binary = path or "ffmpeg"

    def is_available(self) -> bool:
        return shutil.which(self.ffmpeg_binary) is not None

    def build_command(self, options: FFmpegOptions) -> list[str]:
        args = options.to_args()
        return [self.ffmpeg_binary, *args]

    def run(
        self,
        options: FFmpegOptions,
        log: Optional[LogCallback] = None,
        on_finish: Optional[FinishCallback] = None,
    ) -> None:
        if not self.is_available():
            message = "ffmpeg not found in PATH."
            if log:
                log(message + "\n")
            if on_finish:
                on_finish(False, message)
            return

        cmd = self.build_command(options)
        if log:
            log(f"$ {' '.join(cmd)}\n")

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert self._process.stdout is not None
            for line in iter(self._process.stdout.readline, ""):
                if log:
                    log(line)
            self._process.stdout.close()
            return_code = self._process.wait()
            success = return_code == 0
            if on_finish:
                on_finish(success, None if success else f"ffmpeg exited {return_code}")
        except KeyboardInterrupt:
            if on_finish:
                on_finish(False, "Cancelled")
        except FileNotFoundError:
            message = "ffmpeg executable missing."
            if log:
                log(message + "\n")
            if on_finish:
                on_finish(False, message)
        except Exception as exc:  # pragma: no cover
            if log:
                log(f"Error: {exc}\n")
            if on_finish:
                on_finish(False, str(exc))
        finally:
            self._process = None

    def cancel(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()

