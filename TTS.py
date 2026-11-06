import os
import io
import wave
import queue
import threading
import requests
import numpy as np
import sounddevice as sd


# ========== 1. 请求 TTS，返回 WAV bytes ==========
def text2voice(text,sentiment_label,sentiment_confidence):
    url = "http://127.0.0.1:9880/tts"
    if float(sentiment_confidence)<0.4:
        sentiment_level = "low"
    elif 0.4 <= float(sentiment_confidence) < 0.6:
        sentiment_level = "middle"
    else:
        sentiment_level = "high"
    with open("refVoice/"+sentiment_label+"/"+sentiment_label+"_"+sentiment_level+".txt", "r", encoding="utf-8") as f:
        prompt_text = f.read().strip()  # strip() 去掉首尾空白/换行
    """API里必须填绝对地址"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    print(current_dir)
    ref_audio_path = current_dir+"/refVoice/"+sentiment_label+"/"+sentiment_label+"_"+sentiment_level+".wav"
    params = {
        "text": text,
        "text_lang": "zh",
        "ref_audio_path": ref_audio_path,
        "prompt_lang": "ja",
        "prompt_text": prompt_text,
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    return r.content   # 这里返回的是二进制的WAV格式

# ========== 2. 把 WAV bytes 解码成 numpy 数组 ==========
# 输入 WAV 二进制，输出 (audio, samplerate, channels)。
def _wav_bytes_to_numpy(wav_bytes):
    """
    返回 (audio, samplerate, channels)
    audio 形状为 (n_samples, channels)，dtype=float32，取值范围约 [-1, 1]
    """
    """
    wave.open能够直接打开的文件只有两种形式
    1.文件路径字符串，例如 "a.wav" —— 此时 wave 会自己去 open() 这个路径。
    2.已经打开的文件对象（file-like object）—— 有 read()、seek()、tell() 等方法的对象。
    3.io.BytesIO 是标准库里提供的一个类，它把一段内存字节包装成「文件对象」，让你可以像操作真实文件一样操作内存里的数据
    4.'rb'是权限控制字符，表示以二进制只读方式打开。
    5.使用wave打开的文件会识别为wav格式，所以wf就是wav格式的音频。
    """
    with (wave.open(io.BytesIO(wav_bytes), 'rb') as wf):
        # 获取该音频的各项属性：声道，每样本字节数，采样率，总帧数，原始PCM字节
        n_channels = wf.getnchannels()# 通道数：1（单）或 2（立体声）
        samp_width = wf.getsampwidth()# 每个采样点占几个字节1 / 2 / 4
        framerate = wf.getframerate()# 采样率（每秒多少帧）
        n_frames = wf.getnframes()# 总帧数
        raw = wf.readframes(n_frames)# 原始 PCM 字节
        """
        raw 只是一串没有类型信息的字节。同样是 b'\x01\x02'：
        按 int16 解释 → 一个数 513
        按 uint8 解释 → 两个数 [1, 2]
        按 int32 解释 → 报错（字节不够）或错值
        所以必须先知道位深，才能决定怎么解释这串字节。samp_width 就是从 WAV 头里读出来的位深信息。
        """
        if samp_width == 2:# 如果一个采样点是两个字节，那么数据格式就是int16
            dtype = np.int16
            max_val = 32768.0
        elif samp_width == 4:# 如果一个采样点是四个字节，那么数据格式就是int32
            dtype = np.int32
            max_val = 2147483648.0
        elif samp_width == 1:# 如果一个采样点是一个字节，那么数据格式就是unit8*（无符号）
            # 8-bit WAV 是无符号的
            dtype = np.uint8
            max_val = 128.0
        else:
            raise ValueError(f"不支持的位深: {samp_width}")
        # np.frombuffer表示从缓冲区内读取转换为np数组，括号内的第一个参数就是"缓冲区"
        audio = np.frombuffer(raw, dtype=dtype).astype(np.float32)

        # 归一化，将数值范围限制在[-1,1]
        # 一位无符号的这一种比较特殊因为uint8的范围是[0,255]，但是我们要把不同位数的采样信息都归一化为[-1,1]之间。所以这里先减去128让数值范围变为[-128,128]
        if samp_width == 1:
            audio = (audio - 128.0) / max_val
        else:
            audio = audio / max_val
        #重构一维数组，让它变成播放器要的二位形状，'-1'表示系统自己算，用总数除以第二个参数来算出第一个参数，这里就是算出每个通道内的采样数
        if n_channels > 1:
            audio = audio.reshape(-1, n_channels)
        else:
            audio = audio.reshape(-1, 1)
        #返回处理好的音频，帧率和通道数
        return audio, framerate, n_channels


# ========== 3. 全局播放队列 + 停止标志 ==========
_play_queue = queue.Queue()
_stop_flag = threading.Event()


# ========== 4. 播放线程：持续打开 OutputStream ==========
def _playback_worker(samplerate, channels, block_ms=50):
    """
    常驻播放线程：不断从 _play_queue 取音频写入 OutputStream，
    队列空时写静音，保持流不关闭，从而消除段间开关延迟。
    """
    block_size = int(samplerate * block_ms / 1000)
    # 预设一个在play_queue中没有音频时播放的音频，用来防止播放器关闭导致音频卡顿
    silence = np.zeros((block_size, channels), dtype=np.float32)

    with sd.OutputStream(
        samplerate=samplerate,
        channels=channels,
        dtype='float32',
        blocksize=block_size,   # 固定块大小，减少抖动
        latency='low',          # 低延迟
    ) as stream:
        while not _stop_flag.is_set():
            try:
                data = _play_queue.get(timeout=block_ms / 1000.0)#除一千是为了统一单位为秒
                if data is None:        # 结束信号
                    break
                stream.write(data)
            except queue.Empty:
                stream.write(silence)   # 没数据就写静音，流保持开启


# ========== 5. 主入口：切片 → 流式连续播放 ==========
def segments2voice(segments,sentiment_label,sentiment_confidence):
    """
    把所有切片音频写入同一个持续打开的音频流，
    段与段之间无开关延迟，听感像一整段话。
    """
    # 过滤掉不满足条件(能否成功删减两侧的空字符)的数据，完成之后以s的形式再次存入到segment
    segments = [s for s in segments if s.strip()]
    """
    上面这一行等价于：
    result = []
    for s in segments:
        if s.strip():
            result.append(s)
    segments = result
    """
    if not segments:
        return

    # 清空上一轮遗留状态
    _stop_flag.clear()
    while not _play_queue.empty():
        try:
            _play_queue.get_nowait()
        except queue.Empty:
            break

    total = len(segments)

    # ---- 先请求第一段，用于确定采样率和声道数 ----
    try:
        first_bytes = text2voice(segments[0],sentiment_label,sentiment_confidence)
        first_audio, samplerate, channels = _wav_bytes_to_numpy(first_bytes)
        print(f"[1/{total}] 播放：{segments[0]}")
    except Exception as e:
        print(f"第 1 段合成失败：{e}")
        return

    # ---- 启动播放线程（OutputStream 常驻）----
    play_thread = threading.Thread(
        target=_playback_worker,# 创建的进程
        args=(samplerate, channels),# 设置播放器参数
        daemon=True,
        # daemon=True 把线程标记为守护线程（daemon thread）。它的特性是：
        # 主程序退出时，守护线程会被强制结束，不管它有没有跑完。
        # 反过来，非守护线程（daemon=False，默认）会阻止主程序退出，直到它自己结束。
    )
    play_thread.start()
    # 第一段入队
    _play_queue.put(first_audio)

    # ---- 后台预取剩余片段 ----
    def producer():
        # segment里面元素的编号是从0开始的，我们已经去读了0号数据，所以这里从1开始，但是对外显示的序号是从1开始的，所以设置的start=2
        for idx, seg in enumerate(segments[1:], start=2):
            if _stop_flag.is_set():
                break
            try:
                audio_bytes = text2voice(seg,sentiment_label,sentiment_confidence)
                arr, sr, ch = _wav_bytes_to_numpy(audio_bytes)
                if sr != samplerate:
                    print(f"警告：第 {idx} 段采样率 {sr} != {samplerate}，可能变调")
                if ch != channels:
                    # 简单处理：声道数不一致时，复制/取第一个声道
                    if ch == 1 and channels == 2:
                        arr = np.repeat(arr, 2, axis=1)
                    elif ch == 2 and channels == 1:
                        arr = arr.mean(axis=1, keepdims=True)
                print(f"[{idx}/{total}] 预取：{seg}")
                _play_queue.put(arr)
            except Exception as e:
                print(f"第 {idx} 段合成失败：{e}")
        _play_queue.put(None)   # 结束信号

    producer_thread = threading.Thread(target=producer, daemon=True)
    producer_thread.start()

    # ---- 等待全部播完 ----
    # 主线程会在执行到.join()的时候停住等待producer_thread执行完成之后再往下走
    producer_thread.join()
    play_thread.join()


# ========== 6. 可选：中断播放 ==========
def stop_playback():
    """外部想强制停止时调用"""
    _stop_flag.set()
    # 塞一个 None 唤醒可能阻塞在 get 的播放线程
    _play_queue.put(None)