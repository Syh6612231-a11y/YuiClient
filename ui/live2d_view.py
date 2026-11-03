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
它不画界面、不存业务数据，唯一职责：接收网页 JS 的调用，转成 Qt 信号。
可以把它想成一个只对外开 4 个"窗口"的对象，网页只能通过这 4 个窗口递消息进来。

网页JS	@Slot 方法 onReady/onError/onLog/onTap	JS能调用的入口
Python	Signal 信号 ready/failed/logged/tapped	Python能监听的出口
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
class Live2DView(QWidget): # python的继承是直接写在括号内的
    """承载 Live2D 网页舞台，并提供动作、表情、Toast 等调用接口。"""

    model_loaded = Signal(str)
    model_failed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(420, 480)
        self._loaded = False
        self._closed = False

        self._server = AssetServer(ROOT) # 这里的ROOT在上面定义了，是项目的根目录。
        self._view = QWebEngineView(self) # 创建内嵌浏览器控件，父对象为 self，生命周期随 Live2DView 一起销毁.
        self._view.setContextMenuPolicy(Qt.NoContextMenu) # 禁用右键菜单（默认浏览器右键菜单会暴露"重新加载/检查元素"等，不适合正式界面）

        layout = QVBoxLayout(self) # 创建一个列容器来存放live2D
        layout.setContentsMargins(0, 0, 0, 0) # 边距设置为 0
        layout.addWidget(self._view)() #将浏览器控件添加到容器内

        settings = self._view.settings() # 获取到浏览器控件的settings
        """初始化浏览器控件设置"""
        settings.setAttribute(QWebEngineSettings.WebGLEnabled, True) # 开启 WebGL（浏览器里的 3D/GPU 图形 API）
        settings.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, True) # 开启 2D Canvas 硬件加速（用 GPU 加速 <canvas> 的 2D 绘制）
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True) # 允许本地内容（file:// 或本地服务提供的页面）发起对远程 URL 的访问（fetch/XHR/加载远程资源）
        settings.setAttribute(QWebEngineSettings.PlaybackRequiresUserGesture, False) # 允许无需用户交互（点击/按键）就自动播放音视频

        """
        _Bridge 是"网页里的 JavaScript"和"Python 代码"之间的双向通信中转站。
        它让网页能主动通知 Python（模型加载好了、加载失败、被点击了），从而把网页内部发生的事情变成 Python 世界里的信号。
        """
        self._bridge = _Bridge(self) # 创建Bridge——用来链接JS
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
        # 这个字符串是一段 JavaScript 代码，会被 _run 送进网页里执行。它不是 Python，也不是文件路径，而是要在 QWebEngineView 加载的 HTML 页面的 JS 环境里运行的脚本
        self._run("window.Live2DStage && window.Live2DStage.randomMotion()")
        # 先获取到浏览器上面的那个“window.Live2DStage”对象然后再执行它的randomMotion()方法播放一个随机动作

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
