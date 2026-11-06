"""无音频设备的 TTS 播放器冒烟测试（用假音频流验证分段、电平和错误处理）。"""

from __future__ import annotations

import io
import sys
import wave
from pathlib import Path

import numpy as np
import requests
from PySide6.QtCore import QCoreApplication, QObject, QTimer, Slot

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backend.tts_player as tts_player  # noqa: E402
from backend.tts_player import TTSPlayer  # noqa: E402


class DummyStream:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *exc_info) -> bool:
        return False

    def write(self, data) -> None:
        return None


class Collector(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.events: list = []

    @Slot()
    def on_started(self) -> None:
        self.events.append("started")

    @Slot()
    def on_finished(self) -> None:
        self.events.append("finished")
        QCoreApplication.quit()

    @Slot(str)
    def on_failed(self, message: str) -> None:
        self.events.append(("failed", message))

    @Slot(float)
    def on_level(self, value: float) -> None:
        self.events.append(("level", value))


def make_wav(seconds: float = 0.2, rate: int = 32000, amplitude: float = 0.15) -> bytes:
    frames = int(rate * seconds)
    positions = np.arange(frames) / rate
    samples = (np.sin(2 * np.pi * 220 * positions) * amplitude * 32767).astype(np.int16)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(samples.tobytes())
    return buffer.getvalue()


def run_case(app: QCoreApplication, synthesize, segments: list[str]) -> list:
    collector = Collector()
    player = TTSPlayer(segments, synthesize=synthesize)
    player.started.connect(collector.on_started)
    player.finished.connect(collector.on_finished)
    player.failed.connect(collector.on_failed)
    player.level.connect(collector.on_level)
    player.start()
    QTimer.singleShot(6000, app.quit)
    app.exec()
    return collector.events


def main() -> int:
    tts_player.sd.OutputStream = DummyStream
    app = QCoreApplication([])

    ok_events = run_case(app, lambda text: make_wav(), ["第一句。", "第二句。"])
    ok = (
        "started" in ok_events
        and "finished" in ok_events
        and not any(isinstance(event, tuple) and event[0] == "failed" for event in ok_events)
        and any(isinstance(event, tuple) and event[0] == "level" and event[1] > 0 for event in ok_events)
    )
    print("成功路径：", [event if not isinstance(event, tuple) else event[0] for event in ok_events][:10])
    print("  电平事件数：", sum(1 for event in ok_events if isinstance(event, tuple) and event[0] == "level"))

    def broken(text: str):
        raise requests.exceptions.ConnectionError("connection refused")

    error_events = run_case(app, broken, ["你好。"])
    messages = [event[1] for event in error_events if isinstance(event, tuple) and event[0] == "failed"]
    print("失败路径：", messages)
    error_ok = bool(messages) and "未启动" in messages[0]

    print("RESULT:", "PASS" if ok and error_ok else "FAIL")
    return 0 if ok and error_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
