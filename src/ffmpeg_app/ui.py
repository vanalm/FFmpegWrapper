from __future__ import annotations

import sys

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .ffmpeg_runner import FFmpegRunner
from .options import PRESETS, FFmpegOptions, suggest_output_path
from .settings import AppSettings


class FFmpegWorker(QObject):
    log_line = Signal(str)
    finished = Signal(bool, object)  # success, error message or None

    def __init__(self, runner: FFmpegRunner, options: FFmpegOptions) -> None:
        super().__init__()
        self.runner = runner
        self.options = options

    def run(self) -> None:
        self.runner.run(
            self.options,
            log=self.log_line.emit,
            on_finish=lambda success, message: self.finished.emit(success, message),
        )

    def cancel(self) -> None:
        self.runner.cancel()


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self._settings = settings
        self.result_settings: Optional[AppSettings] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout()
        grid = QGridLayout()
        row = 0

        self.audio_checkbox = QCheckBox("Include audio by default")
        self.audio_checkbox.setChecked(self._settings.include_audio)
        grid.addWidget(self.audio_checkbox, row, 0, 1, 2)
        row += 1

        self.crf_slider = QSlider(Qt.Horizontal)
        self.crf_slider.setRange(15, 35)
        self.crf_slider.setValue(self._settings.crf)
        self.crf_value = QLabel(str(self._settings.crf))
        grid.addWidget(QLabel("Default CRF"), row, 0)
        grid.addWidget(self.crf_slider, row, 1)
        grid.addWidget(self.crf_value, row, 2)
        row += 1

        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(1, 20)
        self.speed_slider.setValue(self._settings.speed)
        self.speed_value = QLabel(f"{self._settings.speed}x")
        grid.addWidget(QLabel("Default speed"), row, 0)
        grid.addWidget(self.speed_slider, row, 1)
        grid.addWidget(self.speed_value, row, 2)
        row += 1

        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(0, 240)
        self.fps_spin.setValue(self._settings.fps or 0)
        grid.addWidget(QLabel("Default FPS (0 = source)"), row, 0)
        grid.addWidget(self.fps_spin, row, 1)
        row += 1

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(PRESETS)
        self.preset_combo.setCurrentText(self._settings.preset)
        grid.addWidget(QLabel("Default preset"), row, 0)
        grid.addWidget(self.preset_combo, row, 1)
        row += 1

        self.suffix_edit = QLineEdit(self._settings.default_suffix)
        grid.addWidget(QLabel("Default output suffix"), row, 0)
        grid.addWidget(self.suffix_edit, row, 1, 1, 2)
        row += 1

        self.ffmpeg_path_edit = QLineEdit(self._settings.ffmpeg_path or "")
        ffmpeg_row = QHBoxLayout()
        ffmpeg_row.addWidget(self.ffmpeg_path_edit)
        browse = QPushButton("Browse")
        browse.clicked.connect(self._choose_ffmpeg)
        clear = QPushButton("Reset")
        clear.clicked.connect(lambda: self.ffmpeg_path_edit.setText(""))
        ffmpeg_row.addWidget(browse)
        ffmpeg_row.addWidget(clear)
        grid.addWidget(QLabel("Custom ffmpeg path"), row, 0)
        grid.addLayout(ffmpeg_row, row, 1, 1, 2)
        row += 1

        layout.addLayout(grid)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        save_btn.clicked.connect(self._save)
        cancel_btn.clicked.connect(self.reject)
        buttons.addStretch()
        buttons.addWidget(cancel_btn)
        buttons.addWidget(save_btn)
        layout.addLayout(buttons)

        self.setLayout(layout)

        self.crf_slider.valueChanged.connect(lambda v: self.crf_value.setText(str(v)))
        self.speed_slider.valueChanged.connect(
            lambda v: self.speed_value.setText(f"{v}x")
        )

    def _choose_ffmpeg(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select ffmpeg binary")
        if path:
            self.ffmpeg_path_edit.setText(path)

    def _save(self) -> None:
        ffmpeg_path = self.ffmpeg_path_edit.text().strip() or None
        if ffmpeg_path and not Path(ffmpeg_path).exists():
            QMessageBox.warning(self, "Invalid path", "ffmpeg path does not exist.")
            return

        self.result_settings = AppSettings(
            include_audio=self.audio_checkbox.isChecked(),
            crf=self.crf_slider.value(),
            speed=self.speed_slider.value(),
            fps=self.fps_spin.value() or None,
            preset=self.preset_combo.currentText(),
            default_suffix=self.suffix_edit.text().strip() or "processed",
            ffmpeg_path=ffmpeg_path,
        )
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("FFmpeg Wrapper")
        self.setAcceptDrops(True)
        self.settings = AppSettings.load()
        self.options = FFmpegOptions(
            include_audio=self.settings.include_audio,
            crf=self.settings.crf,
            speed=self.settings.speed,
            fps=self.settings.fps,
            preset=self.settings.preset,
        )
        self.runner = FFmpegRunner()
        self.runner.set_ffmpeg_binary(self.settings.ffmpeg_path)
        self.worker_thread: Optional[QThread] = None
        self.worker: Optional[FFmpegWorker] = None
        self._updating_output = False
        self._last_suggested_output: Optional[str] = None

        self._build_ui()
        self._wire_signals()
        self._apply_settings_to_controls()
        self._refresh_output_path()

    def _build_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout()

        # Input row + settings gear
        input_row = QHBoxLayout()
        self.settings_btn = QToolButton()
        self.settings_btn.setText("⚙")
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Drop a video file or browse…")
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._choose_input)
        input_row.addWidget(self.settings_btn)
        input_row.addWidget(QLabel("Input"))
        input_row.addWidget(self.input_edit)
        input_row.addWidget(browse_btn)
        layout.addLayout(input_row)

        # Output row
        output_row = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Auto-filled based on input and options")
        output_row.addWidget(QLabel("Output"))
        output_row.addWidget(self.output_edit)
        layout.addLayout(output_row)

        # Options grid
        grid = QGridLayout()
        row = 0

        self.audio_checkbox = QCheckBox("Include audio")
        self.audio_checkbox.setChecked(True)
        grid.addWidget(self.audio_checkbox, row, 0, 1, 2)
        row += 1

        self.crf_slider = QSlider(Qt.Horizontal)
        self.crf_slider.setRange(15, 35)
        self.crf_slider.setValue(self.options.crf)
        self.crf_value = QLabel(str(self.options.crf))
        grid.addWidget(QLabel("Compression (CRF)"), row, 0)
        grid.addWidget(self.crf_slider, row, 1)
        grid.addWidget(self.crf_value, row, 2)
        row += 1

        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(1, 20)
        self.speed_slider.setValue(self.options.speed)
        self.speed_value = QLabel(f"{self.options.speed}x")
        grid.addWidget(QLabel("Speed"), row, 0)
        grid.addWidget(self.speed_slider, row, 1)
        grid.addWidget(self.speed_value, row, 2)
        row += 1

        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(0, 240)
        self.fps_spin.setValue(0)
        grid.addWidget(QLabel("FPS (0 = source)"), row, 0)
        grid.addWidget(self.fps_spin, row, 1)
        row += 1

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(PRESETS)
        self.preset_combo.setCurrentText(self.options.preset)
        grid.addWidget(QLabel("Preset"), row, 0)
        grid.addWidget(self.preset_combo, row, 1)
        row += 1

        layout.addLayout(grid)

        # Buttons
        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("Run")
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        btn_row.addStretch()
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

        # Log
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(QLabel("Log"))
        layout.addWidget(self.log_view)

        central.setLayout(layout)
        self.setCentralWidget(central)

    def _wire_signals(self) -> None:
        self.input_edit.textChanged.connect(self._on_input_changed)
        self.output_edit.textChanged.connect(self._on_output_changed)
        self.audio_checkbox.stateChanged.connect(self._refresh_output_path)
        self.crf_slider.valueChanged.connect(self._on_crf_changed)
        self.speed_slider.valueChanged.connect(self._on_speed_changed)
        self.fps_spin.valueChanged.connect(self._refresh_output_path)
        self.preset_combo.currentTextChanged.connect(self._refresh_output_path)
        self.run_btn.clicked.connect(self._start_run)
        self.cancel_btn.clicked.connect(self._cancel_run)
        self.settings_btn.clicked.connect(self._open_settings)

    # Drag and drop
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                self.input_edit.setText(urls[0].toLocalFile())
        else:
            super().dropEvent(event)

    def _choose_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select input file")
        if path:
            self.input_edit.setText(path)

    def _on_input_changed(self, text: str) -> None:
        if text:
            self.options.input_path = Path(text)
            self._refresh_output_path()

    def _on_output_changed(self, text: str) -> None:
        if self._updating_output:
            return
        self.options.output_path = Path(text) if text else None

    def _on_crf_changed(self, value: int) -> None:
        self.crf_value.setText(str(value))
        self.options.crf = value
        self._refresh_output_path()

    def _on_speed_changed(self, value: int) -> None:
        self.speed_value.setText(f"{value}x")
        self.options.speed = value
        self._refresh_output_path()

    def _refresh_output_path(self) -> None:
        self.options.include_audio = self.audio_checkbox.isChecked()
        self.options.fps = self.fps_spin.value() or None
        self.options.preset = self.preset_combo.currentText()
        if self.options.input_path:
            suggested = suggest_output_path(
                self.options.input_path, self.options, default_suffix=self.settings.default_suffix
            )
            suggested_str = str(suggested)
            current = self.output_edit.text().strip()
            should_replace = not current or current == (self._last_suggested_output or "")
            self._last_suggested_output = suggested_str
            if should_replace:
                self._updating_output = True
                self.output_edit.setText(suggested_str)
                self._updating_output = False

    def _start_run(self) -> None:
        input_text = self.input_edit.text().strip()
        if not input_text:
            QMessageBox.warning(self, "Missing input", "Please select an input file.")
            return

        opts = FFmpegOptions(
            input_path=Path(input_text),
            output_path=Path(self.output_edit.text()) if self.output_edit.text() else None,
            include_audio=self.audio_checkbox.isChecked(),
            crf=self.crf_slider.value(),
            speed=self.speed_slider.value(),
            fps=self.fps_spin.value() or None,
            preset=self.preset_combo.currentText(),
        )

        self.log_view.clear()
        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)

        self.worker_thread = QThread()
        self.worker = FFmpegWorker(self.runner, opts)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.log_line.connect(self._append_log)
        self.worker.finished.connect(self._on_finished)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self._cleanup_worker)
        self.worker_thread.start()

    def _cancel_run(self) -> None:
        if self.worker:
            self.worker.cancel()
        self.cancel_btn.setEnabled(False)

    def _on_finished(self, success: bool, message: object) -> None:
        if message:
            self._append_log(f"{message}\n")
        if success:
            self._append_log("Done.\n")
        else:
            self._append_log("Failed.\n")
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    def _cleanup_worker(self) -> None:
        self.worker = None
        self.worker_thread = None

    def _append_log(self, text: str) -> None:
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_view.setTextCursor(cursor)
        self.log_view.insertPlainText(text)
        self.log_view.ensureCursorVisible()

    def _apply_settings_to_controls(self) -> None:
        self.audio_checkbox.setChecked(self.settings.include_audio)
        self.crf_slider.setValue(self.settings.crf)
        self.speed_slider.setValue(self.settings.speed)
        self.fps_spin.setValue(self.settings.fps or 0)
        self.preset_combo.setCurrentText(self.settings.preset)

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == QDialog.Accepted and dialog.result_settings:
            self.settings = dialog.result_settings
            self.settings.save()
            self.runner.set_ffmpeg_binary(self.settings.ffmpeg_path)
            self._apply_settings_to_controls()
            self._refresh_output_path()


def launch() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(720, 520)
    window.show()
    sys.exit(app.exec())

