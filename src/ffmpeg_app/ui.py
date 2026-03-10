from __future__ import annotations

import sys
import traceback
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
    QGroupBox,
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
from .notes_generator import run_notes_generation
from .options import PRESETS, FFmpegOptions, suggest_output_path
from .settings import MODELS_BY_PROVIDER, PROVIDERS, AppSettings
from .transcriber import run_transcription


class FFmpegWorker(QObject):
    log_line = Signal(str)
    finished = Signal(bool, object)

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


class PostProcessWorker(QObject):
    """Runs transcript and/or notes generation on a background thread."""

    log_line = Signal(str)
    finished = Signal(bool, object)

    def __init__(
        self,
        input_path: Path,
        output_dir: Path,
        settings: AppSettings,
        do_transcript: bool,
        do_notes: bool,
    ) -> None:
        super().__init__()
        self.input_path = input_path
        self.output_dir = output_dir
        self.settings = settings
        self.do_transcript = do_transcript
        self.do_notes = do_notes
        self._cancelled = False

    def run(self) -> None:
        try:
            transcript_text: Optional[str] = None

            if self.do_transcript or self.do_notes:
                if not self.settings.deepgram_api_key:
                    self.finished.emit(False, "Deepgram API key not set. Check Settings.")
                    return

                self.log_line.emit("\n--- Transcription ---\n")
                transcript_text, _ = run_transcription(
                    self.input_path,
                    self.output_dir,
                    api_key=self.settings.deepgram_api_key,
                    ffmpeg_binary=self.settings.ffmpeg_path,
                    log=self.log_line.emit,
                )

            if self._cancelled:
                self.finished.emit(False, "Cancelled")
                return

            if self.do_notes:
                if not self.settings.openai_api_key:
                    self.finished.emit(False, "OpenAI API key not set. Check Settings.")
                    return

                self.log_line.emit("\n--- Meeting Notes ---\n")
                run_notes_generation(
                    transcript=transcript_text or "",
                    input_path=self.input_path,
                    output_dir=self.output_dir,
                    system_prompt=self.settings.notes_system_prompt,
                    api_key=self.settings.openai_api_key,
                    model=self.settings.notes_model,
                    log=self.log_line.emit,
                )

            self.finished.emit(True, None)
        except Exception as exc:
            self.log_line.emit(f"Error: {exc}\n{traceback.format_exc()}\n")
            self.finished.emit(False, str(exc))

    def cancel(self) -> None:
        self._cancelled = True


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self._settings = settings
        self.result_settings: Optional[AppSettings] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout()

        # --- FFmpeg defaults ---
        ffmpeg_group = QGroupBox("FFmpeg Defaults")
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

        ffmpeg_group.setLayout(grid)
        layout.addWidget(ffmpeg_group)

        # --- API Keys ---
        keys_group = QGroupBox("API Keys")
        keys_grid = QGridLayout()
        kr = 0

        self.deepgram_key_edit = QLineEdit(self._settings.deepgram_api_key or "")
        self.deepgram_key_edit.setEchoMode(QLineEdit.Password)
        self.deepgram_key_edit.setPlaceholderText("Deepgram API key")
        keys_grid.addWidget(QLabel("Deepgram"), kr, 0)
        keys_grid.addWidget(self.deepgram_key_edit, kr, 1)
        kr += 1

        self.openai_key_edit = QLineEdit(self._settings.openai_api_key or "")
        self.openai_key_edit.setEchoMode(QLineEdit.Password)
        self.openai_key_edit.setPlaceholderText("OpenAI API key")
        keys_grid.addWidget(QLabel("OpenAI"), kr, 0)
        keys_grid.addWidget(self.openai_key_edit, kr, 1)
        kr += 1

        self.gemini_key_edit = QLineEdit(self._settings.gemini_api_key or "")
        self.gemini_key_edit.setEchoMode(QLineEdit.Password)
        self.gemini_key_edit.setPlaceholderText("Gemini API key")
        keys_grid.addWidget(QLabel("Gemini"), kr, 0)
        keys_grid.addWidget(self.gemini_key_edit, kr, 1)
        kr += 1

        keys_group.setLayout(keys_grid)
        layout.addWidget(keys_group)

        # --- Notes provider / model / prompt ---
        notes_group = QGroupBox("Meeting Notes")
        notes_grid = QGridLayout()
        nr = 0

        self.provider_combo = QComboBox()
        self.provider_combo.addItems([p.capitalize() for p in PROVIDERS])
        self.provider_combo.setCurrentText(self._settings.notes_provider.capitalize())
        notes_grid.addWidget(QLabel("Provider"), nr, 0)
        notes_grid.addWidget(self.provider_combo, nr, 1)
        nr += 1

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setInsertPolicy(QComboBox.NoInsert)
        self._populate_models()
        notes_grid.addWidget(QLabel("Model"), nr, 0)
        notes_grid.addWidget(self.model_combo, nr, 1)
        nr += 1

        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlainText(self._settings.notes_system_prompt)
        self.prompt_edit.setMinimumHeight(100)
        notes_grid.addWidget(QLabel("System prompt"), nr, 0, Qt.AlignTop)
        notes_grid.addWidget(self.prompt_edit, nr, 1)
        nr += 1

        notes_group.setLayout(notes_grid)
        layout.addWidget(notes_group)

        # --- Buttons ---
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

        # Signals
        self.crf_slider.valueChanged.connect(lambda v: self.crf_value.setText(str(v)))
        self.speed_slider.valueChanged.connect(
            lambda v: self.speed_value.setText(f"{v}x")
        )
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)

    def _populate_models(self) -> None:
        provider = self.provider_combo.currentText().lower()
        models = list(MODELS_BY_PROVIDER.get(provider, []))
        saved = self._settings.notes_model
        if saved and saved not in models:
            models.append(saved)
        self.model_combo.clear()
        self.model_combo.addItems(models)
        self.model_combo.setCurrentText(saved)

    def _on_provider_changed(self, _text: str) -> None:
        self._populate_models()

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
            transcript_enabled=self._settings.transcript_enabled,
            notes_enabled=self._settings.notes_enabled,
            deepgram_api_key=self.deepgram_key_edit.text().strip() or None,
            openai_api_key=self.openai_key_edit.text().strip() or None,
            gemini_api_key=self.gemini_key_edit.text().strip() or None,
            notes_provider=self.provider_combo.currentText().lower(),
            notes_model=self.model_combo.currentText().strip() or "gpt-4o",
            notes_system_prompt=self.prompt_edit.toPlainText().strip()
            or self._settings.notes_system_prompt,
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
        self.pp_thread: Optional[QThread] = None
        self.pp_worker: Optional[PostProcessWorker] = None
        self._updating_output = False
        self._last_suggested_output: Optional[str] = None
        self._pending_transcript = False
        self._pending_notes = False

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
        self.settings_btn.setText("\u2699")
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Drop a video file or browse\u2026")
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

        # AI feature toggles
        ai_row = QHBoxLayout()
        self.transcript_checkbox = QCheckBox("Generate Transcript")
        self.transcript_checkbox.setChecked(self.settings.transcript_enabled)
        self.notes_checkbox = QCheckBox("Generate Meeting Notes")
        self.notes_checkbox.setChecked(self.settings.notes_enabled)
        ai_row.addWidget(self.transcript_checkbox)
        ai_row.addWidget(self.notes_checkbox)
        ai_row.addStretch()
        layout.addLayout(ai_row)

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
        self.notes_checkbox.stateChanged.connect(self._on_notes_toggled)

    def _on_notes_toggled(self, state: int) -> None:
        if state == Qt.Checked.value and not self.transcript_checkbox.isChecked():
            self.transcript_checkbox.setChecked(True)

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

        do_transcript = self.transcript_checkbox.isChecked()
        do_notes = self.notes_checkbox.isChecked()

        if do_transcript and not self.settings.deepgram_api_key:
            QMessageBox.warning(
                self, "Missing API key",
                "Deepgram API key is required for transcription. Set it in Settings.",
            )
            return
        if do_notes and not self.settings.openai_api_key:
            QMessageBox.warning(
                self, "Missing API key",
                "OpenAI API key is required for meeting notes. Set it in Settings.",
            )
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

        self._pending_transcript = do_transcript
        self._pending_notes = do_notes

        self.log_view.clear()
        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)

        self.worker_thread = QThread()
        self.worker = FFmpegWorker(self.runner, opts)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.log_line.connect(self._append_log)
        self.worker.finished.connect(self._on_ffmpeg_finished)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self._cleanup_worker)
        self.worker_thread.start()

    def _cancel_run(self) -> None:
        if self.worker:
            self.worker.cancel()
        if self.pp_worker:
            self.pp_worker.cancel()
        self.cancel_btn.setEnabled(False)

    def _on_ffmpeg_finished(self, success: bool, message: object) -> None:
        if message:
            self._append_log(f"{message}\n")
        if success:
            self._append_log("FFmpeg done.\n")
        else:
            self._append_log("FFmpeg failed.\n")
            self.run_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            return

        if self._pending_transcript or self._pending_notes:
            self._start_post_processing()
        else:
            self._append_log("Done.\n")
            self.run_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)

    def _start_post_processing(self) -> None:
        input_path = Path(self.input_edit.text().strip())
        output_dir = input_path.parent

        self.pp_thread = QThread()
        self.pp_worker = PostProcessWorker(
            input_path=input_path,
            output_dir=output_dir,
            settings=self.settings,
            do_transcript=self._pending_transcript,
            do_notes=self._pending_notes,
        )
        self.pp_worker.moveToThread(self.pp_thread)
        self.pp_thread.started.connect(self.pp_worker.run)
        self.pp_worker.log_line.connect(self._append_log)
        self.pp_worker.finished.connect(self._on_post_process_finished)
        self.pp_worker.finished.connect(self.pp_thread.quit)
        self.pp_thread.finished.connect(self._cleanup_pp_worker)
        self.pp_thread.start()

    def _on_post_process_finished(self, success: bool, message: object) -> None:
        if message:
            self._append_log(f"{message}\n")
        if success:
            self._append_log("All done.\n")
        else:
            self._append_log("Post-processing failed.\n")
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    def _cleanup_worker(self) -> None:
        self.worker = None
        self.worker_thread = None

    def _cleanup_pp_worker(self) -> None:
        self.pp_worker = None
        self.pp_thread = None

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
        self.transcript_checkbox.setChecked(self.settings.transcript_enabled)
        self.notes_checkbox.setChecked(self.settings.notes_enabled)

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
    window.resize(720, 580)
    window.show()
    sys.exit(app.exec())
