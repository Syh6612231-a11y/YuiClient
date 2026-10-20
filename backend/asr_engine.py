"""Qwen3-ASR 本地模型封装。

模型在第一次使用语音输入时才加载，避免拖慢客户端启动；加载后进程内复用。
"""

from __future__ import annotations

import threading
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "voice2text" / "Qwen3-ASR-1___7B"
SAMPLE_RATE = 16000


class ASREngine:
    _singleton: "ASREngine | None" = None
    _singleton_lock = threading.Lock()

    def __init__(self) -> None:
        self._model = None
        self._load_lock = threading.Lock()
        self.device: str | None = None

    @classmethod
    def instance(cls) -> "ASREngine":
        with cls._singleton_lock:
            if cls._singleton is None:
                cls._singleton = cls()
            return cls._singleton

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            if not MODEL_DIR.is_dir():
                raise FileNotFoundError(f"找不到语音识别模型目录：{MODEL_DIR}")

            import torch
            from qwen_asr import Qwen3ASRModel

            if torch.cuda.is_available():
                device, dtype = "cuda:0", torch.bfloat16
            else:
                device, dtype = "cpu", torch.float32

            self._model = Qwen3ASRModel.from_pretrained(
                str(MODEL_DIR),
                dtype=dtype,
                device_map=device,
                max_new_tokens=512,
            )
            self.device = device

    def transcribe(self, samples: np.ndarray, sample_rate: int = SAMPLE_RATE) -> str:
        self.load()
        audio = np.asarray(samples, dtype=np.float32).reshape(-1)
        import torch

        with torch.inference_mode():
            results = self._model.transcribe(audio=(audio, sample_rate), language=None)
        if not results:
            return ""
        return (results[0].text or "").strip()
