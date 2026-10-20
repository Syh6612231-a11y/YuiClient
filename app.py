"""MyDigitalMaid 桌面客户端入口。

左侧 Live2D 舞台，右侧对话面板。当前版本是可运行的界面骨架：
- 已接入原有 socket 协议（127.0.0.1:8888），服务端不在线时自动切换到离线演示模式。
- Live2D 使用 QtWebEngine 承载网页渲染，模型放在 assets/models 下会自动加载。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MyDigitalMaid 对话数字人桌面客户端")
    parser.add_argument("--host", default="127.0.0.1", help="对话服务端地址")
    parser.add_argument("--port", type=int, default=8888, help="对话服务端端口")
    parser.add_argument(
        "--screenshot",
        type=Path,
        default=None,
        help="渲染窗口并保存截图后退出（调试用）",
    )
    parser.add_argument(
        "--demo-chat",
        default=None,
        metavar="TEXT",
        help="启动后自动发送一条消息（调试用）",
    )
    parser.add_argument(
        "--no-speak",
        action="store_true",
        help="启动时关闭自动朗读",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtGui import QFont
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("缺少 PySide6。请先激活项目环境并安装依赖：")
        print("  conda activate MydigitalMaid_client")
        print("  pip install -r requirements-gui.txt")
        return 1

    from ui.main_window import MainWindow
    from ui.theme import apply_theme

    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("MyDigitalMaid")
    app.setOrganizationName("MyDigitalMaid")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    apply_theme(app)

    window = MainWindow(host=args.host, port=args.port, auto_speak=not args.no_speak)
    app.aboutToQuit.connect(window.shutdown)

    screen = app.primaryScreen()
    if screen is not None:
        available = screen.availableGeometry()
        width = min(1280, max(1000, int(available.width() * 0.94)))
        height = min(820, max(650, int(available.height() * 0.92)))
        window.resize(width, height)
    else:
        window.resize(1280, 820)
    window.show()

    if args.demo_chat:
        QTimer.singleShot(1800, lambda: window.demo_send(args.demo_chat))

    if args.screenshot:
        target = args.screenshot

        def capture() -> None:
            target.parent.mkdir(parents=True, exist_ok=True)
            pixmap = window.grab()
            pixmap.save(str(target))
            print(f"[app] screenshot saved to {target}")
            app.quit()

        QTimer.singleShot(6000 if args.demo_chat else 4500, capture)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
