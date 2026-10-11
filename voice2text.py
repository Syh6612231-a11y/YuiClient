import numpy as np
import speech_recognition as sr
from qwen_asr import Qwen3ASRModel
import torch
from pathlib import Path
def v2t(model):
    # 获取识别器
    recognizer = sr.Recognizer()
    recognizer.pause_threshold = 2 # 停止说话之后1.5秒视为结束输入
    mic = sr.Microphone(sample_rate=16000)
    with mic as source:
        print("正在校准环境噪音，请保持安静 1 秒...")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        print("准备就绪！请开始说话（按 Ctrl+C 退出）...")

        while True:
            try:
                # ===== 从麦克风采集音频 =====
                audio = recognizer.listen(source, phrase_time_limit=60)
                print("识别中...")

                # ===== Qwen3-ASR 识别（直接传 numpy 数组，无需落盘） =====
                raw_data = audio.get_raw_data(convert_rate=16000, convert_width=2)
                # 16-bit PCM 字节 → float32 numpy 数组，范围 [-1, 1]
                samples = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0

                # 识别（循环内）
                results = model.transcribe(
                    audio=(samples, 16000),
                    language=None,
                )
                text = results[0].text.strip() if results else ""
                if not text:
                    print("（未识别到有效内容）")
                    continue
                else:
                    return text
                print(f"[{lang}] 玉舟哥哥说：{text}")
            except sr.WaitTimeoutError:
                print("（等待说话中...）")
                continue
            except sr.UnknownValueError:
                print("（未能识别音频内容）")
                continue
            except sr.RequestError as e:
                print(f"（请求 API 失败，请检查网络：{e}）")
                break
            except KeyboardInterrupt:
                print("\n程序已退出。")
                break