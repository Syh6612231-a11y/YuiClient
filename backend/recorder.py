"""麦克风录音：简单 VAD，自动在说完后停止，返回 16k 单声道 float32 波形。"""

from __future__ import annotations

import threading
import time
from typing import Callable

import numpy as np

SAMPLE_RATE = 16000
BLOCK_MS = 30


def _rms(block: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(block), dtype=np.float64) + 1e-12))


def _resample(samples: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if source_rate == target_rate or samples.size == 0:
        return samples.astype(np.float32, copy=False)
    duration = samples.size / source_rate
    target_count = max(1, int(duration * target_rate))
    source_positions = np.linspace(0.0, duration, samples.size, endpoint=False)
    target_positions = np.linspace(0.0, duration, target_count, endpoint=False)
    return np.interp(target_positions, source_positions, samples).astype(np.float32)


def record_utterance(
    cancel_event: threading.Event | None = None,
    finish_event: threading.Event | None = None,
    on_level: Callable[[float], None] | None = None,
    start_timeout: float = 8.0,
    silence_seconds: float = 1.3,
    max_seconds: float = 30.0,
) -> np.ndarray | None:
    """录一句话。

    - 等待说话最多 ``start_timeout`` 秒；
    - 检测到人声后，静音 ``silence_seconds`` 秒自动结束；
    - ``finish_event`` 被置位时提前结束并返回已录内容；
    - ``cancel_event`` 被置位时放弃录音并返回 None。
    """
    import sounddevice as sd

    cancel = cancel_event or threading.Event()
    finish = finish_event or threading.Event()

    samplerate = SAMPLE_RATE
    block_size = int(samplerate * BLOCK_MS / 1000)
    stream = None
    try:
        stream = sd.InputStream(
            samplerate=samplerate,
            channels=1,
            dtype="float32",
            blocksize=block_size,
        )
        stream.start()
    except Exception:
        if stream is not None:
            try:
                stream.close()
            except Exception:
                pass
        # 部分声卡不接受 16k，退回到设备默认采样率，录完再重采样
        try:
            info = sd.query_devices(kind="input")
            samplerate = int(info["default_samplerate"])
            block_size = max(160, int(samplerate * BLOCK_MS / 1000))
            stream = sd.InputStream(
                samplerate=samplerate,
                channels=1,
                dtype="float32",
                blocksize=block_size,
            )
            stream.start()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"无法打开麦克风：{exc}") from exc

    def read_block() -> np.ndarray:
        try:
            data, _overflowed = stream.read(block_size)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"录音失败：{exc}") from exc
        mono = np.asarray(data[:, 0] if data.ndim > 1 else data, dtype=np.float32)
        if on_level is not None:
            try:
                on_level(min(1.0, _rms(mono) * 8.0))
            except Exception:
                pass
        return mono

    try:
        noise = [_rms(read_block()) for _ in range(6)]
        if cancel.is_set():
            return None
        threshold = max(0.015, min(float(np.median(noise)) * 3.0, 0.06))

        pre_roll: list[np.ndarray] = []
        speech_run = 0
        started = False
        deadline = time.monotonic() + start_timeout

        while time.monotonic() < deadline:
            if cancel.is_set() or finish.is_set():
                return None
            mono = read_block()
            pre_roll.append(mono)
            if len(pre_roll) > 6:
                pre_roll.pop(0)
            if _rms(mono) > threshold:
                speech_run += 1
                if speech_run >= 2:
                    started = True
                    break
            else:
                speech_run = 0

        if not started:
            return None

        frames: list[np.ndarray] = list(pre_roll)
        voiced_frames = sum(1 for frame in pre_roll if _rms(frame) > threshold)
        silence = 0.0
        recorded = sum(len(frame) for frame in frames) / samplerate

        while recorded < max_seconds:
            if cancel.is_set():
                return None
            if finish.is_set():
                break
            mono = read_block()
            frames.append(mono)
            recorded += len(mono) / samplerate
            if _rms(mono) > threshold:
                voiced_frames += 1
                silence = 0.0
            else:
                silence += len(mono) / samplerate
                if silence >= silence_seconds:
                    break

        # 至少 180ms 人声，过滤掉鼠标点击、设备爆音之类的瞬时噪声
        if voiced_frames < 6:
            return None

        # 只裁掉最后一段人声之后的静音，保留约 5 帧尾音
        last_voiced = -1
        for index, frame in enumerate(frames):
            if _rms(frame) > threshold:
                last_voiced = index
        if last_voiced >= 0:
            frames = frames[: min(len(frames), last_voiced + 5)]

        if not frames:
            return None
        samples = np.concatenate(frames).astype(np.float32)
        if samplerate != SAMPLE_RATE:
            samples = _resample(samples, samplerate, SAMPLE_RATE)
        return samples
    finally:
        try:
            stream.stop()
        except Exception:
            pass
        try:
            stream.close()
        except Exception:
            pass
