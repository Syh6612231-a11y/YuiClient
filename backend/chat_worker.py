"""对话后端线程。

沿用 client.py 的协议：
- 每轮先发送 `文本 + "$"`，再发送 `家庭状态 + "$"`；
- 服务端按顺序回两条以 `$` 结尾的消息：回复文本、控制码字符串（如 "13"）。

服务端未启动时进入离线演示模式，用本地规则模拟回复，方便单独调试界面。
"""

from __future__ import annotations

import queue
import random
import socket
import time

from PySide6.QtCore import QThread, Signal

FAREWELL_WORDS = ("再见", "拜拜", "晚安", "先这样")
GREETING_WORDS = ("你好", "嗨", "在吗", "早上好", "晚上好", "下午好")

DEMO_GENERIC = [
    "嗯嗯，我在听呢。玉舟哥哥今天过得怎么样？",
    "好呀～都听你的。",
    "这个问题让我想想…不过只要是你说的，我都记在心里。",
    "嘿嘿，被你这么一说，我有点开心。",
    "我在的，一直都在。你想让我做点什么吗？",
]


def demo_reply(text: str) -> tuple[str, str]:
    """离线模式下的关键词回复，返回 (回复, 控制码)。"""
    message = text.strip()

    if any(word in message for word in FAREWELL_WORDS):
        return random.choice(["下次见啦，记得想我哦。", "好，那我先安静一会儿，随时叫我。"]), ""
    if any(word in message for word in GREETING_WORDS):
        return "玉舟哥哥，晚上好呀。今天也辛苦啦，想聊点什么？", ""

    if "灯" in message:
        if any(word in message for word in ("关", "灭", "暗")):
            return "好，我把灯关掉。这样安静一点，也更适合聊天。", "2"
        return "灯已经打开啦，亮堂堂的～", "1"

    if "空调" in message:
        if any(word in message for word in ("关", "停", "冷")):
            return "空调关掉了，温度慢慢会回来。", "4"
        return "空调打开咯，一会儿就凉快了。", "3"

    if "茶" in message:
        return "茶泡好啦，小心烫，慢慢喝。", "5"
    if "饭" in message or "吃" in message:
        return "饭做好啦！虽然只是简单的家常菜，但要好好吃完哦。", "6"
    if "打扫" in message or "卫生" in message or "收拾" in message:
        return "房间已经收拾干净了，你看看还满意吗？", "7"

    return random.choice(DEMO_GENERIC), ""


class ChatWorker(QThread):
    connected = Signal(bool, str)
    reply_received = Signal(str)
    control_received = Signal(str)
    thinking = Signal(bool)
    failed = Signal(str)

    def __init__(self, host: str = "127.0.0.1", port: int = 8888, parent=None) -> None:
        super().__init__(parent)
        self.host = host
        self.port = port

        self._outbox: queue.Queue[tuple[str, str] | None] = queue.Queue()
        self._alive = True
        self._sock: socket.socket | None = None

    # ------------------------------------------------------------------ API
    def send(self, text: str, status_prompt: str) -> None:
        self._outbox.put((text, status_prompt))

    def stop(self) -> None:
        self._alive = False
        self._outbox.put(None)
        sock = self._sock
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass

    # ----------------------------------------------------------------- run
    def run(self) -> None:  # noqa: C901 - 状态机保持在一个函数里更直观
        try:
            self._connect()
            if self._sock is not None:
                self.connected.emit(True, f"{self.host}:{self.port}")
                self._online_loop()
            else:
                self.connected.emit(False, "离线演示模式")
                self._offline_loop()
        finally:
            if self._sock is not None:
                try:
                    self._sock.close()
                except OSError:
                    pass
                self._sock = None

    def _connect(self) -> None:
        try:
            self._sock = socket.create_connection((self.host, self.port), timeout=1.5)
            self._sock.settimeout(0.25)
        except OSError:
            self._sock = None

    # ------------------------------------------------------------- online
    def _online_loop(self) -> None:
        assert self._sock is not None
        buffer = b""
        pending = 0
        waiting_reply = True

        while self._alive:
            if pending == 0:
                try:
                    item = self._outbox.get(timeout=0.15)
                except queue.Empty:
                    continue
                if item is None:
                    break
                text, status_prompt = item
                try:
                    self._sock.sendall((text + "$").encode("utf-8"))
                    self._sock.sendall((status_prompt + "$").encode("utf-8"))
                except OSError as exc:
                    if self._alive:
                        self.failed.emit(f"发送失败：{exc}")
                    break
                pending = 1
                waiting_reply = True
                self.thinking.emit(True)
                continue

            try:
                chunk = self._sock.recv(4096)
            except socket.timeout:
                continue
            except OSError as exc:
                if self._alive:
                    self.failed.emit(f"连接异常：{exc}")
                break

            if not chunk:
                if self._alive:
                    self.failed.emit("服务端已断开连接")
                break

            buffer += chunk
            while b"$" in buffer:
                raw, buffer = buffer.split(b"$", 1)
                message = raw.decode("utf-8", errors="replace")
                if waiting_reply:
                    self.reply_received.emit(message)
                    waiting_reply = False
                else:
                    self.control_received.emit(message)
                    waiting_reply = True
                    pending = 0
                    self.thinking.emit(False)
                    break

    # ------------------------------------------------------------ offline
    def _offline_loop(self) -> None:
        while self._alive:
            try:
                item = self._outbox.get(timeout=0.2)
            except queue.Empty:
                continue
            if item is None:
                break

            text, _status = item
            self.thinking.emit(True)

            delay = random.uniform(0.55, 1.05) + min(len(text) * 0.012, 0.9)
            deadline = time.monotonic() + delay
            while self._alive and time.monotonic() < deadline:
                time.sleep(0.05)
            if not self._alive:
                break

            reply, control = demo_reply(text)
            self.reply_received.emit(reply)
            self.control_received.emit(control)
            self.thinking.emit(False)
