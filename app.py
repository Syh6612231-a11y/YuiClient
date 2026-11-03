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

# args是arguments的缩写，arguments的意思是实参
"""
这个parse_args是用来解析命令行传入的参数的，例如：
python main.py --host 192.168.1.10，这是通过命令行执行的时候的常见输入形式，为了解析“--”后面的“host 192.168.1.10”
需要定义好这个解析函数。
parser.add_argument("--host", default="127.0.0.1", help="对话服务端地址")
上面这一行的意思就是当出现“--host”，就将后面的内容解析为服务器ip
"""
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """
    创建一个 ArgumentParser 对象，负责管理所有参数定义和解析逻辑。
    description=...：设置帮助文本的描述，会在执行 --help 时显示在参数列表上方。
    """
    parser = argparse.ArgumentParser(description="MyDigitalMaid 对话数字人桌面客户端")
    parser.add_argument("--host", default="127.0.0.1", help="对话服务端地址")
    parser.add_argument("--port", type=int, default=8888, help="对话服务端端口")
    parser.add_argument(
        "--no-speak",
        action="store_true",
        help="启动时关闭自动朗读",
    )
    # 返回解析的参数，如果用户没有输出就都采用默认值
    return parser.parse_args(argv)

"""
这里规定了参数名称叫做argv（argument vector），参数类型是string，或者是None，当用户没有传入参数的时候，默认参数为None
->表示返回值类型为int
后面的Syh6612231-ally表示该部分代码的最后一次修改是由这个作者提交的。
"""
def main(argv: list[str]|None = None) -> int:
    args = parse_args(argv)
    # 这里使用的是动态导入，方便检查哪些依赖有缺失
    try:
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtGui import QFont
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("缺少 PySide6。请先激活项目环境并安装依赖：")
        print("conda activate MydigitalMaid_client")
        print("pip install -r requirements-gui.txt")
        return 1

    from ui.main_window import MainWindow
    from ui.theme import apply_theme
    """
    QApplication 是使用 PySide6/PyQt（Qt 的 Python 绑定）开发传统桌面 GUI 程序时，
    必须在程序启动阶段创建的一个核心对象。它负责初始化窗口系统、管理应用级的设置（如字体、样式），并运行那个让程序“保持响应”的事件循环。
    """
    # ————————————————————初始化窗口信息————————————————————
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True) # 设置应用的全局属性
    app = QApplication(sys.argv[:1]) # 设置QT的根对象
    app.setApplicationName("DigitalMaid") # 设置应用名称，是一个应用级的元信息
    app.setOrganizationName("OrganizationName") # 设置组织/公司名称，同样是元信息
    app.setFont(QFont("Microsoft YaHei UI", 10)) # 设置全局默认字体。所有没有单独指定字体的控件都会继承它
    apply_theme(app) #调用项目自定义的主题函数（定义在 ui.theme 模块，前面代码 from ui.theme import apply_theme 已导入）
    # ————————————————————创建窗口————————————————————
    window = MainWindow(host=args.host, port=args.port, auto_speak=not args.no_speak) # 默认设置非no_speak，也就是开启朗读
    app.aboutToQuit.connect(window.shutdown) # 当整个应用程序即将退出时，自动调用 window 的 shutdown() 方法来清理资源
    # ————————————————————自适应调整窗口大小————————————————————
    screen = app.primaryScreen() # 获取屏幕信息
    if screen is not None:
        available = screen.availableGeometry()
        width = min(1280, max(1000, int(available.width() * 0.94)))
        height = min(820, max(650, int(available.height() * 0.92)))
        window.resize(width, height)
        # 成功获取到屏幕信息之后，根据屏幕大小调整窗口大小
    else:
        window.resize(1280, 820)
        # 没获取到屏幕信息就设置为默认大小 1280px×820px
    window.show()
    return app.exec() # 退出时返回一个整数作为退出状态代码

if __name__ == "__main__": # 当这个文件被直接运行时（而不是被当作模块 import），调用 main() 函数。
    raise SystemExit(main())
