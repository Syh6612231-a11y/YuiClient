"""开发自检：不播放音频，直接把嘴型参数拉满，截图确认 Live2D 口型生效。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget  # noqa: E402

from ui.live2d_view import Live2DView  # noqa: E402
from ui.theme import apply_theme  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    apply_theme(app)

    window = QWidget()
    window.resize(700, 900)
    layout = QVBoxLayout(window)
    layout.setContentsMargins(0, 0, 0, 0)
    view = Live2DView()
    layout.addWidget(view)
    window.show()

    def on_loaded(name: str) -> None:
        view.set_speaking(True)
        view.set_mouth(1.0)
        QTimer.singleShot(1800, capture)

    def capture() -> None:
        target = ROOT / "artifacts" / "lipsync.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        window.grab().save(str(target))
        print(f"lipsync screenshot -> {target}")
        app.quit()

    view.model_loaded.connect(on_loaded)
    QTimer.singleShot(15000, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
