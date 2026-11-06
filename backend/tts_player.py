"""TTS 播放器：逐段请求 GPT-SoVITS，连续播放并回报音量用于口型。"""

from __future__ import annotations

import queue
import threading

import numpy as np
import requests
import sounddevice as sd
from PySide6.QtCore import QObject, Signal

import TTS


class TTSPlayer(QObject):
    started = Signal()
    finished = Signal()
    failed = Signal(str)
    level = Signal(float)

    def __init__(self, segments: list[str], synthesize=None, parent=None) -> None:
        super().__init__(parent)
        self._segments = [segment for segment in segments if segment.strip()]
        self._synthesize = synthesize or TTS.text2voice
        self._queue: "queue.Queue[tuple[np.ndarray, int, int] | None]" = queue.Queue()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._errors: list[Exception] = []

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="tts-player", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._queue.put(None)

    # ------------------------------------------------------------------ 内部
    def _produce(self) -> None:
        for segment in self._segments:
            if self._stop_event.is_set():
                break
            try:
                wav_bytes = self._synthesize(segment)
                audio, samplerate, channels = TTS._wav_bytes_to_numpy(wav_bytes)
            except Exception as exc:  # noqa: BLE001
                self._errors.append(exc)
                continue
            if self._stop_event.is_set():
                break
            self._queue.put((audio, samplerate, channels))
        self._queue.put(None)

    def _friendly_error(self) -> str:
        if not self._errors:
            return "没有可朗读的内容"
        error = self._errors[0]
        if isinstance(error, requests.exceptions.ConnectionError):
            return "语音合成服务未启动（127.0.0.1:9880）"
        if isinstance(error, requests.exceptions.Timeout):
            return "语音合成服务响应超时"
        if isinstance(error, requests.exceptions.HTTPError):
            return f"语音合成请求失败：{error}"
        return f"语音合成失败：{error}"

    def _run(self) -> None:
        producer = threading.Thread(target=self._produce, name="tts-producer", daemon=True)
        producer.start()

        first = self._queue.get()
        if first is None:
            if not self._stop_event.is_set():
                self.failed.emit(self._friendly_error())
            self.finished.emit()
            return

        _, samplerate, channels = first
        block_size = max(1, int(samplerate * 0.04))
        try:
            with sd.OutputStream(
                samplerate=samplerate,
                channels=channels,
                dtype="float32",
                blocksize=block_size,
            ) as stream:
                self.started.emit()
                item = first
                while item is not None:
                    if self._stop_event.is_set():
                        break
                    audio, rate, channel_count = item
                    if rate != samplerate:
                        print(f"[TTS] 警告：采样率 {rate} != {samplerate}")
                    if channel_count != channels:
                        if channel_count == 1 and channels == 2:
                            audio = np.repeat(audio, 2, axis=1)
                        elif channel_count == 2 and channels == 1:
                            audio = audio.mean(axis=1, keepdims=True)
                    for start in range(0, len(audio), block_size):
                        if self._stop_event.is_set():
                            break
                        chunk = audio[start : start + block_size]
                        stream.write(chunk)
                        rms = float(np.sqrt(np.mean(np.square(chunk), dtype=np.float64) + 1e-12))
                        self.level.emit(min(1.0, rms * 5.5))
                    item = self._queue.get()
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"音频播放失败：{exc}")
        finally:
            self.level.emit(0.0)
            self.finished.emit()
