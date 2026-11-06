"""右侧对话面板：消息气泡、输入框、连接状态。"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class ChatInput(QPlainTextEdit):
    """单行起步、最多四行自适应的输入框，Enter 发送。"""

    submitted = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ChatInput")
        self.setPlaceholderText("和结衣说点什么…")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setTabChangesFocus(True)
        self.setFixedHeight(54)
        self.textChanged.connect(self._autosize)

    def _autosize(self) -> None:
        height = self.document().size().height()
        self.setFixedHeight(max(54, min(132, int(height) + 28)))

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (
            event.modifiers() & Qt.ShiftModifier
        ):
            event.accept()
            self.submitted.emit()
            return
        super().keyPressEvent(event)


class MessageBubble(QWidget):
    """一条聊天气泡；assistant 左侧带头像，user 右侧高亮。"""

    def __init__(self, role: str, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setTextFormat(Qt.PlainText)
        bubble.setTextInteractionFlags(Qt.TextSelectableByMouse)
        bubble.setMaximumWidth(430)
        bubble.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        bubble.setObjectName("UserBubble" if role == "user" else "AssistantBubble")

        if role == "user":
            layout.addStretch(1)
            layout.addWidget(bubble, 0, Qt.AlignTop)
        else:
            layout.addWidget(self._avatar(), 0, Qt.AlignTop)
            layout.addWidget(bubble, 0, Qt.AlignTop)
            layout.addStretch(1)

    @staticmethod
    def _avatar() -> QLabel:
        avatar = QLabel("结")
        avatar.setFixedSize(32, 32)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
            " stop:0 #ff7aa8, stop:1 #7c9cff);"
            "border-radius: 16px; color: #26101b;"
            "font-weight: 700; font-size: 13px;"
        )
        return avatar


class TypingBubble(QWidget):
    """结衣正在输入的小动画。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(MessageBubble._avatar(), 0, Qt.AlignTop)

        self._label = QLabel("正在输入")
        self._label.setObjectName("TypingLabel")
        layout.addWidget(self._label, 0, Qt.AlignTop)
        layout.addStretch(1)

        self._step = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(420)

    def _tick(self) -> None:
        self._step = (self._step + 1) % 4
        self._label.setText("正在输入" + "·" * self._step)


class ChatPanel(QFrame):
    send_message = Signal(str)
    voice_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setMinimumWidth(380)
        self._typing: TypingBubble | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(12)

        root.addLayout(self._build_header())
        root.addWidget(self._build_messages(), 1)
        root.addLayout(self._build_input())

    # ---------------------------------------------------------------- header
    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)

        avatar = QLabel("结")
        avatar.setFixedSize(40, 40)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
            " stop:0 #ff7aa8, stop:1 #7c9cff);"
            "border-radius: 20px; color: #26101b;"
            "font-weight: 700; font-size: 16px;"
        )

        name = QLabel("由比滨结衣")
        name.setStyleSheet("font-size: 15px; font-weight: 600; color: #f4f6fb;")

        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #f0b45e; font-size: 9px;")
        self.status_text = QLabel("连接中…")
        self.status_text.setObjectName("Muted")

        status_row = QHBoxLayout()
        status_row.setSpacing(4)
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.addWidget(self.status_dot)
        status_row.addWidget(self.status_text)
        status_row.addStretch(1)

        info = QVBoxLayout()
        info.setSpacing(1)
        info.addWidget(name)
        info.addLayout(status_row)

        self.clear_btn = QPushButton("清空")
        self.clear_btn.setObjectName("GhostButton")
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.clicked.connect(self.clear_messages)

        row.addWidget(avatar)
        row.addLayout(info, 1)
        row.addWidget(self.clear_btn)
        return row

    # -------------------------------------------------------------- messages
    def _build_messages(self) -> QScrollArea:
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        host = QWidget()
        host.setObjectName("MessagesHost")
        self._messages = QVBoxLayout(host)
        self._messages.setContentsMargins(2, 4, 6, 4)
        self._messages.setSpacing(8)
        self._messages.addStretch(1)

        self._scroll.setWidget(host)
        return self._scroll

    # ----------------------------------------------------------------- input
    def _build_input(self) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(6)

        row = QHBoxLayout()
        row.setSpacing(8)

        self.voice_btn = QPushButton("语音")
        self.voice_btn.setObjectName("GhostButton")
        self.voice_btn.setToolTip("语音输入（Qwen3-ASR）")
        self.voice_btn.setCursor(Qt.PointingHandCursor)
        self.voice_btn.setMinimumHeight(38)
        self.voice_btn.setFixedWidth(64)
        self.voice_btn.clicked.connect(self.voice_clicked.emit)

        self.input = ChatInput()
        self.input.submitted.connect(self._submit)

        self.send_btn = QPushButton("发送")
        self.send_btn.setObjectName("AccentButton")
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setEnabled(False)
        self.send_btn.clicked.connect(self._submit)
        self.input.textChanged.connect(self._sync_send_button)

        row.addWidget(self.voice_btn, 0, Qt.AlignBottom)
        row.addWidget(self.input, 1)
        row.addWidget(self.send_btn, 0, Qt.AlignBottom)

        self.hint = QLabel("Enter 发送 · Shift+Enter 换行")
        self.hint.setObjectName("Hint")
        self.hint.setAlignment(Qt.AlignRight)

        column.addLayout(row)
        column.addWidget(self.hint)
        return column

    # --------------------------------------------------------------- actions
    def _submit(self) -> None:
        text = self.input.toPlainText().strip()
        if not text:
            return
        self.input.clear()
        self.send_message.emit(text)

    def send_text(self, text: str) -> None:
        """供调试/自动化调用：填入输入框并立即发送。"""
        self.input.setPlainText(text)
        self._submit()

    def _sync_send_button(self) -> None:
        self.send_btn.setEnabled(bool(self.input.toPlainText().strip()))

    def add_message(self, role: str, text: str) -> None:
        self._insert(self._new_bubble(role, text))

    def _new_bubble(self, role: str, text: str) -> MessageBubble:
        return MessageBubble(role, text)

    def add_system(self, text: str) -> None:
        note = QLabel(text)
        note.setObjectName("SystemNote")
        note.setWordWrap(True)
        note.setAlignment(Qt.AlignCenter)
        self._insert(note)

    def _insert(self, widget: QWidget) -> None:
        index = self._messages.count() - 1
        if self._typing is not None:
            typing_index = self._messages.indexOf(self._typing)
            if typing_index >= 0:
                index = typing_index
        self._messages.insertWidget(max(0, index), widget)
        self.scroll_to_bottom()

    def show_typing(self) -> None:
        if self._typing is not None:
            return
        self._typing = TypingBubble()
        self._insert(self._typing)

    def hide_typing(self) -> None:
        if self._typing is None:
            return
        self._typing.setParent(None)
        self._typing.deleteLater()
        self._typing = None

    def clear_messages(self) -> None:
        self.hide_typing()
        while self._messages.count() > 1:
            item = self._messages.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def set_status(self, online: bool, text: str) -> None:
        color = "#59d99b" if online else "#f0b45e"
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 9px;")
        self.status_text.setText(text)

    def set_voice_mode(self, mode: str) -> None:
        """切换语音按钮与输入区提示：idle/listening/loading/recognizing/speaking。"""
        labels = {
            "idle": "语音",
            "listening": "停止",
            "loading": "加载中",
            "recognizing": "识别中",
            "speaking": "语音",
        }
        self.voice_btn.setText(labels.get(mode, "语音"))
        self.voice_btn.setEnabled(mode not in ("loading", "recognizing"))

        if mode == "listening":
            self.voice_btn.setStyleSheet(
                "QPushButton {"
                " background-color: #2a1a24;"
                " color: #ffb3cc;"
                " border: 1px solid #ff7aa8;"
                " border-radius: 10px;"
                " padding: 7px 12px;"
                " font-size: 12px;"
                " font-weight: 600; }"
            )
            self.hint.setText("正在聆听…再次点击「停止」结束")
        elif mode == "speaking":
            self.voice_btn.setStyleSheet("")
            self.hint.setText("正在朗读…点击「语音」可打断")
        elif mode == "loading":
            self.voice_btn.setStyleSheet("")
            self.hint.setText("首次加载语音模型，请稍候…")
        elif mode == "recognizing":
            self.voice_btn.setStyleSheet("")
            self.hint.setText("正在识别语音…")
        else:
            self.voice_btn.setStyleSheet("")
            self.hint.setText("Enter 发送 · Shift+Enter 换行")

    def scroll_to_bottom(self) -> None:
        def _scroll() -> None:
            bar = self._scroll.verticalScrollBar()
            bar.setValue(bar.maximum())

        QTimer.singleShot(0, _scroll)
