"""全局深色主题。"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

ACCENT = "#ff7aa8"
ACCENT_SOFT = "#7c9cff"
TEXT = "#e9edf7"
MUTED = "#8b94aa"
OK = "#59d99b"
WARN = "#f0b45e"

QSS = """
QWidget {
    color: #e9edf7;
    font-family: "Microsoft YaHei UI", "Segoe UI", "PingFang SC", sans-serif;
    font-size: 13px;
}
QWidget#Root {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #090d16, stop:0.45 #0d1424, stop:1 #161b30);
}
QMainWindow {
    background: #090d16;
}

QFrame#Card {
    background-color: #101828;
    border: 1px solid #1e2940;
    border-radius: 18px;
}
QFrame#BrandMark {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ff7aa8, stop:1 #7c9cff);
    border-radius: 10px;
}
QLabel#BrandTitle {
    font-size: 16px;
    font-weight: 600;
    color: #f4f6fb;
}
QLabel#BrandSub {
    color: #7f89a0;
    font-size: 11px;
}
QLabel#StatusPill {
    color: #f0b45e;
    background-color: #141c2e;
    border: 1px solid #263149;
    border-radius: 11px;
    padding: 5px 12px;
    font-size: 12px;
}
QLabel#StageName {
    font-size: 19px;
    font-weight: 700;
    letter-spacing: 1px;
    color: #f7f8fc;
}
QLabel#Tag {
    color: #ffb3cc;
    background-color: #2a1a24;
    border: 1px solid #4d2a3b;
    border-radius: 8px;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 600;
}
QLabel#Muted {
    color: #8b94aa;
    font-size: 12px;
}
QLabel#Hint {
    color: #6f7a92;
    font-size: 11px;
}
QLabel#SystemNote {
    color: #69748d;
    font-size: 11px;
}
QLabel#UserBubble {
    background-color: #ff7aa8;
    color: #26101b;
    border-radius: 14px;
    padding: 9px 13px;
    font-size: 13px;
}
QLabel#AssistantBubble {
    background-color: #1a2338;
    color: #e9edf7;
    border: 1px solid #263149;
    border-radius: 14px;
    padding: 9px 13px;
    font-size: 13px;
}
QLabel#TypingLabel {
    color: #9aa4bb;
    background-color: #1a2338;
    border: 1px solid #263149;
    border-radius: 14px;
    padding: 9px 13px;
    font-size: 12px;
}

QPushButton#GhostButton {
    background-color: #151e31;
    color: #aeb8cd;
    border: 1px solid #263149;
    border-radius: 10px;
    padding: 7px 14px;
    font-size: 12px;
}
QPushButton#GhostButton:hover {
    background-color: #1b2740;
    border-color: #3a4a70;
    color: #e9edf7;
}
QPushButton#GhostButton:pressed {
    background-color: #222f4c;
}
QPushButton#GhostButton:checked {
    background-color: #2a1a24;
    border-color: #ff7aa8;
    color: #ffb3cc;
}
QPushButton#GhostButton:disabled {
    background-color: #121a2a;
    border-color: #1d2740;
    color: #5d6780;
}
QPushButton#AccentButton {
    background-color: #ff7aa8;
    color: #26101b;
    border: none;
    border-radius: 11px;
    padding: 9px 20px;
    font-weight: 600;
}
QPushButton#AccentButton:hover {
    background-color: #ff93b9;
}
QPushButton#AccentButton:pressed {
    background-color: #ef6898;
}
QPushButton#AccentButton:disabled {
    background-color: #232b3e;
    color: #66718a;
}
QToolButton#MicButton {
    background-color: #151e31;
    border: 1px solid #263149;
    border-radius: 11px;
    padding: 8px;
    font-size: 16px;
}
QToolButton#MicButton:hover {
    background-color: #1b2740;
    border-color: #3a4a70;
}

QPlainTextEdit#ChatInput {
    background-color: #0c1322;
    border: 1px solid #263149;
    border-radius: 11px;
    padding: 7px 10px;
    color: #e9edf7;
    font-size: 13px;
    selection-background-color: #ff7aa8;
    selection-color: #26101b;
}
QPlainTextEdit#ChatInput:focus {
    border-color: #3d4d78;
}

QScrollArea, QWidget#MessagesHost {
    background: transparent;
    border: none;
}
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 2px 0;
}
QScrollBar::handle:vertical {
    background: #2a3550;
    border-radius: 4px;
    min-height: 28px;
}
QScrollBar::handle:vertical:hover {
    background: #3a4a70;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QToolTip {
    background-color: #1a2338;
    color: #e9edf7;
    border: 1px solid #2c3a5a;
    padding: 4px 8px;
}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#090d16"))
    palette.setColor(QPalette.WindowText, QColor(TEXT))
    palette.setColor(QPalette.Base, QColor("#0c1322"))
    palette.setColor(QPalette.AlternateBase, QColor("#101828"))
    palette.setColor(QPalette.Text, QColor(TEXT))
    palette.setColor(QPalette.Button, QColor("#151e31"))
    palette.setColor(QPalette.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.HighlightedText, QColor("#26101b"))
    palette.setColor(QPalette.ToolTipBase, QColor("#1a2338"))
    palette.setColor(QPalette.ToolTipText, QColor(TEXT))
    app.setPalette(palette)
    app.setStyleSheet(QSS)
