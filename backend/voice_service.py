"""语音输入服务：后台线程完成「加载模型 -> 录音 -> 识别」，通过 Qt 信号回报。"""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal

from backend.asr_engine import ASREngine
from backend.recorder import record_utterance


def _friendly_error(exc: Exception) -> str:
    if isinstance(exc, FileNotFoundError):
        return str(exc)
    text = str(exc)
    lowered = text.lower()
    if "out of memory" in lowered or "cuda" in lowered:
        return f"语音识别模型加载失败（显存或驱动问题）：{text}"
    if "麦克风" in text:
        return text
    return f"语音识别失败：{text}"


class VoiceService(QObject):
    state_changed = Signal(str)  # loading / listening / recognizing / idle
    transcribed = Signal(str)
    failed = Signal(str)
    level = Signal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cancel = threading.Event()
        self._finish = threading.Event()
        self._active = False
        self._lock = threading.Lock()

    @property
    def active(self) -> bool:
        return self._active

    def start(self) -> None:
        with self._lock:
            if self._active:
                return
            self._active = True
            self._cancel.clear()
            self._finish.clear()
        threading.Thread(target=self._run, name="voice-service", daemon=True).start()

    def finish_recording(self) -> None:
        """用户主动结束录音：保留已录内容并继续识别。"""
        self._finish.set()

    def cancel(self) -> None:
        self._cancel.set()
        self._finish.set()

    def _emit(self, signal, *args) -> None:
        if self._cancel.is_set():
            return
        try:
            signal.emit(*args)
        except RuntimeError:
            pass

    def _run(self) -> None:
        try:
            engine = ASREngine.instance()
            if not engine.is_loaded:
                self._emit(self.state_changed, "loading")
            engine.load()
            if self._cancel.is_set():
                return
            self._emit(self.state_changed, "listening")

            samples = record_utterance(
                cancel_event=self._cancel,
                finish_event=self._finish,
                on_level=self.level.emit,
            )
            if samples is None:
                if not self._cancel.is_set():
                    self._emit(self.failed, "没有听到说话，再试一次吧。")
                return

            self._emit(self.state_changed, "recognizing")
            text = engine.transcribe(samples)
            if self._cancel.is_set():
                return
            if text:
                self._emit(self.transcribed, text)
            else:
                self._emit(self.failed, "没有识别到内容，再说一次吧。")
        except Exception as exc:  # noqa: BLE001
            if not self._cancel.is_set():
                self._emit(self.failed, _friendly_error(exc))
        finally:
            self._active = False
            if not self._cancel.is_set():
                try:
                    self.state_changed.emit("idle")
                except RuntimeError:
                    pass
