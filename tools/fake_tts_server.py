"""本地假 TTS 服务，用于没有 GPT-SoVITS 时联调语音回复。

启动：
    python tools/fake_tts_server.py --port 9880

它会对 /tts 返回一段轻音 WAV（默认 3.5 秒），方便验证播放、口型和状态切换。
"""

from __future__ import annotations

import argparse
import io
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np

SAMPLE_RATE = 32000


def build_wav(seconds: float, frequency: float = 220.0, amplitude: float = 0.02) -> bytes:
    frames = max(1, int(SAMPLE_RATE * seconds))
    positions = np.arange(frames) / SAMPLE_RATE
    samples = (np.sin(2 * np.pi * frequency * positions) * amplitude * 32767).astype(np.int16)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(samples.tobytes())
    return buffer.getvalue()


class Handler(BaseHTTPRequestHandler):
    wav_bytes = b""

    def do_GET(self) -> None:  # noqa: N802
        if not self.path.startswith("/tts"):
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(self.wav_bytes)))
        self.end_headers()
        self.wfile.write(self.wav_bytes)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        print(f"[fake-tts] {self.command} {self.path.split('?')[0]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="本地假 TTS 服务")
    parser.add_argument("--port", type=int, default=9880)
    parser.add_argument("--seconds", type=float, default=3.5)
    args = parser.parse_args()

    Handler.wav_bytes = build_wav(args.seconds)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"[fake-tts] listening on http://127.0.0.1:{args.port} ({args.seconds}s wav)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
