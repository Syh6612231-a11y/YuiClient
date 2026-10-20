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


class MainWindow(QMainWindow):
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8888,
        auto_speak: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("MyDigitalMaid · 对话数字人")
        self.setMinimumSize(960, 640)
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

    # ------------------------------------------------------------------- ui
    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        layout.addLayout(self._build_topbar())

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(14)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_stage_card())
        splitter.addWidget(self._build_chat_card())
        splitter.setStretchFactor(0, 58)
        splitter.setStretchFactor(1, 42)
        splitter.setSizes([720, 520])
        layout.addWidget(splitter, 1)

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

    def _build_stage_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        card.setMinimumWidth(460)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(12)

        head = QHBoxLayout()
        head.setSpacing(8)

        name = QLabel("由比滨结衣")
        name.setObjectName("StageName")
        tag = QLabel("LIVE2D")
        tag.setObjectName("Tag")

        subtitle = QLabel("Cubism 3/4 · WebGL 舞台")
        subtitle.setObjectName("Muted")

        head.addWidget(name)
        head.addWidget(tag, 0, Qt.AlignVCenter)
        head.addStretch(1)
        head.addWidget(subtitle)
        layout.addLayout(head)

        self.stage = Live2DView()
        self.stage.model_loaded.connect(self._on_model_loaded)
        self.stage.model_failed.connect(self._on_model_failed)
        layout.addWidget(self.stage, 1)

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
            "玉舟哥哥，晚上好呀～我是结衣。今天也辛苦啦，想聊点什么？",
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
