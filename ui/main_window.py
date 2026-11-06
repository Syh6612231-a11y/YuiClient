"""主窗口：左侧 Live2D 舞台，右侧对话面板。"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

import actions
from backend.chat_worker import ChatWorker
from backend.tts_player import TTSPlayer
from backend.voice_service import VoiceService
from myTools import split_by_chinese
from ui.chat_panel import ChatPanel
from ui.live2d_view import Live2DView
# 这里不是实际控制动作的地方，只是提供一个人类可读的标签
ACTION_LABELS = {
    0: "待机",
    1: "开灯",
    2: "关灯",
    3: "打开空调",
    4: "关闭空调",
    5: "泡茶",
    6: "做饭",
    7: "打扫卫生",
}

"""
MainWindow 是整个应用的总控器（Controller），它本身不实现具体功能，而是：
1. 搭建 UI 布局（顶部状态栏 + 左右分栏）
2. 持有并协调若干后端组件：ChatWorker（对话）、VoiceService（语音识别）、TTSPlayer（语音合成）、Live2DView（舞台）、ChatPanel（对话面板）
3. 通过 Qt 的信号槽（signal/slot）机制把各组件串起来
4. 管理应用生命周期（启动、关闭、资源释放）
"""
# 定义一个类 MainWindow，继承自 QMainWindow。QMainWindow 是 Qt 提供的"主窗口"基类，自带菜单栏、工具栏、状态栏、中心部件等布局能力，适合做应用程序主界面。
class MainWindow(QMainWindow):
    # 构造函数入口，__init__ 是 Python 对象初始化的特殊方法
    def __init__(
        self, # 因为这是实例方法，第一个参数必须是实例自身，惯例命名为 self
        host: str = "127.0.0.1", # 参数 host，类型标注为 str，默认值 "127.0.0.1"
        port: int = 8888, # 参数 port，类型 int，默认 8888
        auto_speak: bool = True, # 参数 auto_speak，类型 bool，默认 True。控制是否在收到回复后自动朗读（TTS）
        parent=None, # Qt 控件的标准 parent 参数，默认 None，表示它是顶层窗口、没有父控件
    ) -> None: # 参数列表结束，返回值标注为 None（构造函数不返回值）。其实不标注也不会报错，但这样写更规范。
        """
        *构造函数从这里开始*
        self.xxx，可以分成三类：Qt 基类自带的、程序员自定义的、通过继承获得但这里只是调用的.
        下面的属性都是自定义的，前面加上self是为了区分属性和函数内的普通变量
        """
        super().__init__(parent) # 调用父类 QMainWindow.__init__，并把 parent 传进去。Qt 控件必须先完成父类初始化才能使用，否则会崩溃或报错。这里默认传入的是None
        """先调用父类的构造函数，创建这个界面的地基，下面再初始化我们自定义的参数"""
        self.setWindowTitle("MyDigitalMaid · 对话数字人") # 设置窗口标题栏文字为 "MyDigitalMaid · 对话数字人"
        self.setMinimumSize(960, 640) # 设置窗口最小尺寸：宽 960 像素、高 640 像素
        self._host = host
        self._port = port
        self._home = actions.HomeStatus()
        self._greeted = False
        self._shutdown_done = False

        self._auto_speak = auto_speak
        self._voice_state = "idle"
        self._tts_player: TTSPlayer | None = None
        self._tts_error_shown = False

        self._build_ui()

        self._voice_service = VoiceService(self)
        self._voice_service.state_changed.connect(self._on_voice_state)
        self._voice_service.transcribed.connect(self._on_transcribed)
        self._voice_service.failed.connect(self._on_voice_failed)

        self._start_backend()
        QTimer.singleShot(900, self._greeting)
    """
    定义好构造函数之后就可以通过类名创建实例了
    """
    # --------------------创建主布局--------------------
    def _build_ui(self) -> None: #只有一个参数就是self（当前创建的实例）
        root = QWidget() # 创建一个普通的 QWidget 作为根容器（中心部件）
        root.setObjectName("Root") # 给这个控件设置对象名 "Root"
        self.setCentralWidget(root) # 把这个容器挂载到self上，将它设置为中心控件；传入后，root 的父子关系变为窗口的子控件，窗口销毁时自动销毁它。

        # 创建一个垂直布局 QVBoxLayout，并把它安装到 root 上（构造参数 root 即父控件），之后 addLayout / addWidget 加到 layout 里的东西，会从上到下竖排在 root 中。
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 16, 18, 16) # 设置布局的外边距（内容与容器边缘的空白）：左 18、上 16、右 18、下 16 像素
        layout.setSpacing(12) # 设置布局内各子项之间的间距为 12 像素。
        layout.addLayout(self._build_topbar()) # 调用 self._build_topbar()，它返回一个布局对象（比如水平布局），然后 addLayout 把它作为这个垂直布局的第一行加进去。

        """
        创建一个分栏器 QSplitter，方向为水平（Qt.Horizontal）。
        分栏器把区域横向分成左右两块，中间有可拖拽的分隔条，用户能手动调整两边宽度。
        Qt.Horizontal 表示子项左右排列；若是 Qt.Vertical 则上下排列。
        """
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(14) # 设置分隔条（handle）宽度为 14 像素
        splitter.setChildrenCollapsible(False) # 禁止子项被折叠到 0 宽度

        # ————————————————————调用self当中的两个函数分别创建live2D舞台和聊天框————————————————————
        splitter.addWidget(self._build_stage_card()) # 先创建live2D舞台添加到控件当中（左侧live2D）
        splitter.addWidget(self._build_chat_card()) # 再创建聊天框添加到控件当中（右侧聊天框）
        # —————————————————————————————————————————————————————————————————————————————————
        """
        设置第 0 个子项（左侧 stage）的拉伸因子为 58;
        设置第 1 个子项（右侧 chat）的拉伸因子为 42。
        窗口放大/缩小时，额外空间按拉伸因子比例分配。58 : 42 表示左右大致按 58% : 42% 分配新增空间。
        注意：拉伸因子只在有剩余空间需要分配时起作用，不等于初始尺寸。
        """
        splitter.setStretchFactor(0, 58)
        splitter.setStretchFactor(1, 42)
        splitter.setSizes([720, 520]) # 设置分栏的初始尺寸（像素）：左 720、右 520。

        """
        把分栏器作为控件加到垂直布局里。
        第二个参数 1 是拉伸因子：在 QVBoxLayout 中，splitter 的拉伸因子为 1，而顶部栏（addLayout 时没给拉伸因子，默认 0）。
        效果：窗口变高时，多出来的高度几乎全给分栏器（因为它因子为 1，顶部栏为 0），顶部栏保持自然高度，下方区域撑满剩余空间。这正是典型的“顶部固定栏 + 主体自适应”布局。
        """
        layout.addWidget(splitter, 1)

    # --------------------创建顶部bar--------------------
    def _build_topbar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        mark = QLabel("M")
        mark.setObjectName("BrandMark")
        mark.setFixedSize(36, 36)
        mark.setAlignment(Qt.AlignCenter)
        mark.setStyleSheet("color: #1b0f18; font-size: 17px; font-weight: 800;")

        title = QLabel("MyDigitalMaid")
        title.setObjectName("BrandTitle")
        subtitle = QLabel("对话数字人 · 桌面客户端")
        subtitle.setObjectName("BrandSub")

        text_column = QVBoxLayout()
        text_column.setSpacing(0)
        text_column.addWidget(title)
        text_column.addWidget(subtitle)

        self.top_status = QLabel("● 连接中…")
        self.top_status.setObjectName("StatusPill")
        self.top_status.setAlignment(Qt.AlignCenter)

        row.addWidget(mark)
        row.addLayout(text_column)
        row.addStretch(1)
        row.addWidget(self.top_status)
        return row

    # --------------------创建舞台卡片（live2D）--------------------
    """
    这段方法负责构建界面左半部分（stage / 舞台卡片）：标题栏 + Live2D 模型视图 + 底部控制按钮。返回一个 QFrame，由 _build_ui 加到 QSplitter 左侧
    """
    def _build_stage_card(self) -> QFrame:
        card = QFrame() # 创建一个 QFrame 作为卡片容器。QFrame 是 QWidget 的子类，自带边框/外观支持，适合做"卡片"这种视觉分组块。
        card.setObjectName("Card") # 设置对象名 "Card"，供 QSS 样式表用 #Card { ... } 精确定位（比如设圆角、背景、边框）。调试/测试也能按名查找。
        card.setMinimumWidth(460) # 卡片最小宽度 460 像素。防止用户把分栏拖得太窄导致内容挤压变形。配合分栏的 setChildrenCollapsible(False) 一起保障最小可读性。

        layout = QVBoxLayout(card) # 给 card 安装垂直布局，之后加进去的东西从上到下排列。
        layout.setContentsMargins(18, 16, 18, 14) # 设置布局外边距：左 18、上 16、右 18、下 14（顺序：左、上、右、下）。
        layout.setSpacing(12) # 布局内子项之间的间距 12 像素。区分：contentsMargins 是整体外围留白，spacing 是子项彼此间隔。

        head = QHBoxLayout() # 创建一个水平布局 head，用于安放顶部标签。
        head.setSpacing(8) # 标题行内子项间距 8 像素。

        name = QLabel("由比滨结衣") # 创建标题标签
        name.setObjectName("StageName") # *对象名 "StageName"，QSS 可据此设置字号/颜色/字体（比如大标题样式）*
        tag = QLabel("LIVE2D") # 创建一个小标签显示 "LIVE2D"，通常做成"徽章/角标"样式。
        tag.setObjectName("Tag") # 同上，给该对象命名为“Tag”，QSS 可据此设置字号/颜色/字体（比如大标题样式）

        subtitle = QLabel("Cubism 3/4 · WebGL 舞台")
        subtitle.setObjectName("Muted")

        head.addWidget(name)
        head.addWidget(tag, 0, Qt.AlignVCenter) # 垂直居中对齐。注意这是"对齐方式"参数，控制该控件在所在单元格里怎么对齐。
        head.addStretch(1) # 插入一个弹性空白，拉伸因子 1。 效果：把左边的 name、tag 和右边的 subtitle 推开——左边的靠左，右边的靠右。这是 Qt 里做"两端对齐"的常用手法。
        head.addWidget(subtitle)
        layout.addLayout(head) # 将顶部标签插入到live2D舞台

        """创建live2D外观！！！""" # *****************************************************************************************************************
        self.stage = Live2DView()
        self.stage.model_loaded.connect(self._on_model_loaded)
        self.stage.model_failed.connect(self._on_model_failed)
        layout.addWidget(self.stage, 1)
        """创建live2D外观！！！"""  # *****************************************************************************************************************
        controls = QHBoxLayout()
        controls.setSpacing(8)

        self.wave_btn = self._ghost_button("挥挥手", "播放一个随机动作")
        self.wave_btn.clicked.connect(self.stage.play_random_motion)

        self.expr_btn = self._ghost_button("换个表情", "随机切换模型表情")
        self.expr_btn.clicked.connect(self.stage.random_expression)

        self.react_btn = self._ghost_button("互动一下", "让结衣回应你")
        self.react_btn.clicked.connect(self._interact)

        self.speak_btn = self._ghost_button("朗读", "回复后自动朗读（需要 GPT-SoVITS 服务）")
        self.speak_btn.setCheckable(True)
        self.speak_btn.setChecked(self._auto_speak)
        self.speak_btn.toggled.connect(self._on_auto_speak_toggled)

        hint = QLabel("模型放置于 assets/models/")
        hint.setObjectName("Hint")

        controls.addWidget(self.wave_btn)
        controls.addWidget(self.expr_btn)
        controls.addWidget(self.react_btn)
        controls.addWidget(self.speak_btn)
        controls.addStretch(1)
        controls.addWidget(hint)
        layout.addLayout(controls)
        return card

    # --------------------创建聊天框--------------------
    def _build_chat_card(self) -> ChatPanel:
        self.chat = ChatPanel()
        self.chat.send_message.connect(self._on_send)
        self.chat.voice_clicked.connect(self._on_voice)
        return self.chat

    @staticmethod
    def _ghost_button(text: str, tooltip: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("GhostButton")
        button.setToolTip(tooltip)
        button.setCursor(Qt.PointingHandCursor)
        return button

    # --------------------------------------------------------------- backend
    def _start_backend(self) -> None:
        self._worker = ChatWorker(self._host, self._port, self)
        self._worker.connected.connect(self._on_connected)
        self._worker.reply_received.connect(self._on_reply)
        self._worker.control_received.connect(self._on_control)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_send(self, text: str) -> None:
        self._stop_speaking()
        self.chat.add_message("user", text)
        self.chat.show_typing()
        self._worker.send(text, self._home.to_prompt())

    def _on_reply(self, text: str) -> None:
        self.chat.hide_typing()
        if not text.strip():
            return
        self.chat.add_message("assistant", text)
        self.stage.react()
        if self.speak_btn.isChecked():
            self._speak(text)

    def _on_control(self, codes: str) -> None:
        self.chat.hide_typing()
        labels: list[str] = []
        for char in codes:
            if not char.isdigit():
                continue
            code = int(char)
            if code not in actions.actions:
                continue
            try:
                actions.do_action(self._home, code)
            except Exception as exc:  # pragma: no cover - 防御性处理
                print(f"[动作] 执行失败 code={code}: {exc}")
                continue
            labels.append(ACTION_LABELS.get(code, f"动作{code}"))

        if labels:
            unique = list(dict.fromkeys(labels))
            text = "、".join(unique)
            self.chat.add_system(f"动作 · {text}")
            self.stage.show_toast(text)

    def _on_connected(self, online: bool, detail: str) -> None:
        if online:
            self.chat.set_status(True, "已连接服务端")
            self._set_top_status(True, "已连接")
            self.chat.add_system(f"已连接对话服务端 {detail}")
        else:
            self.chat.set_status(False, "离线演示模式")
            self._set_top_status(False, "离线演示")
            self.chat.add_system("未检测到对话服务端，已进入离线演示模式（回复由本地模拟）")

    def _on_failed(self, message: str) -> None:
        self.chat.hide_typing()
        self.chat.set_status(False, "连接已断开")
        self._set_top_status(False, "离线")
        self.chat.add_system(message)

    def _set_top_status(self, online: bool, text: str) -> None:
        color = "#59d99b" if online else "#f0b45e"
        self.top_status.setText("● " + text)
        self.top_status.setStyleSheet(
            "QLabel#StatusPill {"
            f" color: {color};"
            " background-color: #141c2e;"
            " border: 1px solid #263149;"
            " border-radius: 11px;"
            " padding: 5px 12px;"
            " font-size: 12px; }"
        )

    # ----------------------------------------------------------- 语音输入
    def _on_voice(self) -> None:
        if self._voice_state in ("loading", "recognizing"):
            return
        if self._voice_state == "listening":
            # 用户主动结束这一句，已录内容继续送去识别
            self._voice_service.finish_recording()
            return
        if self._tts_player is not None:
            self._stop_speaking()
        self._voice_service.start()

    def _on_voice_state(self, state: str) -> None:
        self._voice_state = state
        self.chat.set_voice_mode(state)
        if state == "loading":
            self.chat.add_system("正在加载 Qwen3-ASR 语音识别模型，首次使用需要等一会儿…")

    def _on_transcribed(self, text: str) -> None:
        self.chat.set_voice_mode("idle")
        self._on_send(text)

    def _on_voice_failed(self, message: str) -> None:
        self.chat.add_system(message)
        self.chat.set_voice_mode("idle")

    # ----------------------------------------------------------- 语音回复
    def _on_auto_speak_toggled(self, checked: bool) -> None:
        if checked:
            self._tts_error_shown = False
        else:
            self._stop_speaking()

    def _speak(self, text: str) -> None:
        segments = [segment for segment in split_by_chinese(text, limit=12) if segment.strip()]
        if not segments:
            return
        self._stop_speaking()

        player = TTSPlayer(segments, parent=self)
        self._tts_player = player
        player.started.connect(lambda p=player: self._on_tts_started(p))
        player.finished.connect(lambda p=player: self._on_tts_finished(p))
        player.failed.connect(lambda message, p=player: self._on_tts_failed(p, message))
        player.level.connect(self._on_tts_level)
        player.start()

    def _on_tts_started(self, player: TTSPlayer) -> None:
        if player is not self._tts_player:
            return
        self.stage.set_speaking(True)
        self.chat.set_voice_mode("speaking")

    def _on_tts_level(self, value: float) -> None:
        if self._tts_player is not None:
            self.stage.set_mouth(value)

    def _on_tts_finished(self, player: TTSPlayer) -> None:
        if player is not self._tts_player:
            return
        self._tts_player = None
        self.stage.set_speaking(False)
        self.stage.set_mouth(0.0)
        if self._voice_state == "idle":
            self.chat.set_voice_mode("idle")

    def _on_tts_failed(self, player: TTSPlayer, message: str) -> None:
        if player is not self._tts_player:
            return
        self._tts_player = None
        self.stage.set_speaking(False)
        self.stage.set_mouth(0.0)
        if self._voice_state == "idle":
            self.chat.set_voice_mode("idle")
        if not self._tts_error_shown:
            self._tts_error_shown = True
            self.chat.add_system(f"{message}。已关闭自动朗读，可在舞台下方重新开启。")
        self.speak_btn.setChecked(False)

    def _stop_speaking(self) -> None:
        player = self._tts_player
        if player is None:
            return
        self._tts_player = None
        player.stop()
        self.stage.set_speaking(False)
        self.stage.set_mouth(0.0)
        if self._voice_state == "idle":
            self.chat.set_voice_mode("idle")

    # ---------------------------------------------------------------- events
    def _greeting(self) -> None:
        if self._greeted:
            return
        self._greeted = True
        self.chat.add_message(
            "assistant",
            "呀哈啰！团子在这里~o(*￣▽￣*)ブ",
        )

    def _interact(self) -> None:
        self.stage.react()
        self.chat.add_message("assistant", "嗯？我在这里呀，有什么想让我做的吗？")

    def demo_send(self, text: str) -> None:
        """调试入口：模拟用户发一条消息。"""
        self.chat.send_text(text)

    def _on_model_loaded(self, name: str) -> None:
        self.chat.add_system(f"Live2D 模型已加载：{name}")

    def _on_model_failed(self, message: str) -> None:
        self.chat.add_system(f"Live2D 舞台异常：{message}")

    def shutdown(self) -> None:
        if self._shutdown_done:
            return
        self._shutdown_done = True
        try:
            self._voice_service.cancel()
        except Exception:
            pass
        self._stop_speaking()
        try:
            self._worker.stop()
            self._worker.wait(2000)
        except Exception:
            pass
        try:
            self.stage.shutdown()
        except Exception:
            pass

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.shutdown()
        super().closeEvent(event)
