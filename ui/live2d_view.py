"""
左侧 Live2D 舞台：QWebEngineView + QWebChannel 桥接。
这个文件实现左侧 Live2D 舞台：用 QWebEngineView 承载一个 HTML/WebGL 页面，
再通过 QWebChannel 在 JS ↔ Python 之间架桥。它对外暴露 play_random_motion()、random_expression()、react() 等方法，供 _build_stage_card 里的按钮调用。
"""

from __future__ import annotations

import json
import os
import urllib.parse
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

"""导入项目自定义的 AssetServer：一个本地 HTTP 静态资源服务器，用来把 assets/ 下的文件通过 http://127.0.0.1:port/... 提供给网页。"""
from backend.asset_server import AssetServer

ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "assets" / "models"

"""
继承 QObject，因为要被注册进 QWebChannel，必须能承载信号槽。
前缀 _ 表示模块内部使用，外部不该直接实例化。
"""
class _Bridge(QObject):
    """JS -> Python 的回调出口。"""
    # 声明 4 个信号，类型标注在括号里
    ready = Signal(str) # 模型加载成功，携带模型名
    failed = Signal(str) # 加载失败，携带错误信息
    logged = Signal(str) #JS 端日志转发
    tapped = Signal() # 用户点击模型（无参数）

    @Slot(str)
    def onReady(self, name: str) -> None:  # noqa: N802 - 与 JS 端约定名称
        self.ready.emit(name)

    @Slot(str)
    def onError(self, message: str) -> None:  # noqa: N802
        self.failed.emit(message)

    @Slot(str)
    def onLog(self, message: str) -> None:  # noqa: N802
        self.logged.emit(message)

    @Slot()
    def onTap(self) -> None:  # noqa: N802
        self.tapped.emit()

"""下面就是live2D舞台的类了，非常非常重要！！！"""
class Live2DView(QWidget):
    """承载 Live2D 网页舞台，并提供动作、表情、Toast 等调用接口。"""

    model_loaded = Signal(str)
    model_failed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(420, 480)
        self._loaded = False
        self._closed = False

        self._server = AssetServer(ROOT)
        self._view = QWebEngineView(self)
        self._view.setContextMenuPolicy(Qt.NoContextMenu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)

        settings = self._view.settings()
        settings.setAttribute(QWebEngineSettings.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.PlaybackRequiresUserGesture, False)

        self._bridge = _Bridge(self)
        self._bridge.ready.connect(self._on_model_ready)
        self._bridge.failed.connect(self._on_model_failed)
        self._bridge.tapped.connect(lambda: self.react())

        self._channel = QWebChannel(self._view.page())
        self._channel.registerObject("stage", self._bridge)
        self._view.page().setWebChannel(self._channel)

        self._view.loadFinished.connect(self._on_load_finished)
        self._view.load(QUrl(self._page_url()))

    # ------------------------------------------------------------- lifecycle
    def _page_url(self) -> str:
        page = self._server.url("web/live2d.html")
        model = self._find_model()
        if model is not None:
            relative = model.relative_to(ROOT).as_posix()
            page += "?model=" + urllib.parse.quote(self._server.url(relative), safe="")
        return page

    def _find_model(self) -> Path | None:
        override = os.environ.get("MYDIGITALMAID_MODEL")
        if override:
            candidate = Path(override)
            if not candidate.is_absolute():
                candidate = ROOT / candidate
            if candidate.is_file():
                try:
                    candidate.relative_to(ROOT)
                    return candidate
                except ValueError:
                    print(f"[Live2D] 模型必须位于项目目录内：{candidate}")
        if MODELS_DIR.is_dir():
            models = sorted(MODELS_DIR.rglob("*.model3.json"))
            if models:
                return models[0]
        return None

    def _on_load_finished(self, ok: bool) -> None:
        self._loaded = ok
        if not ok:
            self.model_failed.emit("Live2D 页面加载失败")

    def _on_model_ready(self, name: str) -> None:
        print(f"[Live2D] 模型已加载：{name}")
        self.model_loaded.emit(name)

    def _on_model_failed(self, message: str) -> None:
        print(f"[Live2D] 加载失败：{message}")
        self.model_failed.emit(message)

    def shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._server.shutdown()

    # ------------------------------------------------------------------- api
    def _run(self, script: str) -> None:
        if not self._loaded:
            return
        self._view.page().runJavaScript(script)

    def play_random_motion(self) -> None:
        self._run("window.Live2DStage && window.Live2DStage.randomMotion()")

    def random_expression(self) -> None:
        self._run("window.Live2DStage && window.Live2DStage.randomExpression()")

    def react(self) -> None:
        self._run("window.Live2DStage && window.Live2DStage.react()")

    def set_speaking(self, speaking: bool) -> None:
        self._run(
            "window.Live2DStage && window.Live2DStage.setSpeaking(%s)"
            % ("true" if speaking else "false")
        )

    def set_mouth(self, value: float) -> None:
        self._run(
            "window.Live2DStage && window.Live2DStage.setMouth(%s)"
            % json.dumps(float(value))
        )

    def show_toast(self, text: str) -> None:
        self._run(
            "window.Live2DStage && window.Live2DStage.showToast(%s)"
            % json.dumps(text, ensure_ascii=False)
        )
