"""无界面冒烟测试：验证 ChatWorker 与仿真服务端的两条消息协议。"""

from __future__ import annotations

import queue
import socket
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QCoreApplication, QTimer  # noqa: E402

from backend.chat_worker import ChatWorker  # noqa: E402


def fake_server(port_box: "queue.Queue[int]", request_box: dict) -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port_box.put(server.getsockname()[1])

    connection, _ = server.accept()
    buffer = b""
    while buffer.count(b"$") < 2:
        chunk = connection.recv(4096)
        if not chunk:
            break
        buffer += chunk
    request_box["raw"] = buffer.decode("utf-8", errors="replace")

    time.sleep(0.3)
    connection.sendall("收到啦，灯已经打开。$13$".encode("utf-8"))
    time.sleep(0.3)
    connection.close()
    server.close()


def main() -> int:
    port_box: "queue.Queue[int]" = queue.Queue()
    request_box: dict = {}
    threading.Thread(target=fake_server, args=(port_box, request_box), daemon=True).start()
    port = port_box.get(timeout=5)

    app = QCoreApplication([])
    worker = ChatWorker("127.0.0.1", port)

    events: list[tuple[str, str]] = []

    def on_connected(online: bool, detail: str) -> None:
        events.append(("connected", f"{online} {detail}"))

    def on_reply(text: str) -> None:
        events.append(("reply", text))

    def on_control(codes: str) -> None:
        events.append(("control", codes))
        app.quit()

    def on_failed(message: str) -> None:
        events.append(("failed", message))
        app.quit()

    worker.connected.connect(on_connected)
    worker.reply_received.connect(on_reply)
    worker.control_received.connect(on_control)
    worker.failed.connect(on_failed)
    worker.start()
    worker.send("把灯打开", "当前家庭状态：灯关")

    QTimer.singleShot(6000, app.quit)
    app.exec()

    worker.stop()
    worker.wait(1500)

    print("服务端收到：", request_box.get("raw", "<无>").replace("$", "$|"))
    for kind, value in events:
        print(f"事件 {kind}: {value}")

    ok = (
        ("connected", "True") in [(k, v.split()[0]) for k, v in events if k == "connected"]
        and any(k == "reply" and "灯" in v for k, v in events)
        and any(k == "control" and v == "13" for k, v in events)
    )
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
