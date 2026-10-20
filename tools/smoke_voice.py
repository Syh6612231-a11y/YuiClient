"""语音服务状态机冒烟测试：用假录音和假识别模型验证信号顺序。"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import QCoreApplication, QObject, QTimer, Slot

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.voice_service as voice_service  # noqa: E402
from backend.voice_service import VoiceService  # noqa: E402


class FakeEngine:
    is_loaded = True

    def load(self) -> None:
        pass

    def transcribe(self, samples) -> str:
        return "把灯打开"


class FakeASR:
    @classmethod
    def instance(cls) -> FakeEngine:
        return FakeEngine()


class Collector(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.events: list = []

    @Slot(str)
    def on_state(self, state: str) -> None:
        self.events.append(state)

    @Slot(str)
    def on_text(self, text: str) -> None:
        self.events.append(("text", text))
        QTimer.singleShot(200, QCoreApplication.quit)

    @Slot(str)
    def on_error(self, message: str) -> None:
        self.events.append(("error", message))
        QCoreApplication.quit()


def main() -> int:
    voice_service.ASREngine = FakeASR  # type: ignore[assignment]
    voice_service.record_utterance = lambda **kwargs: np.full(16000, 0.02, dtype=np.float32)

    app = QCoreApplication([])
    collector = Collector()
    service = VoiceService()
    service.state_changed.connect(collector.on_state)
    service.transcribed.connect(collector.on_text)
    service.failed.connect(collector.on_error)

    service.start()
    QTimer.singleShot(5000, app.quit)
    app.exec()

    print("状态序列：", collector.events)
    ok = (
        collector.events[:3] == ["listening", "recognizing", ("text", "把灯打开")]
        and collector.events[-1] == "idle"
    )
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
