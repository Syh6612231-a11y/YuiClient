"""本地静态资源服务。

QtWebEngine 里用 file:// 打开页面时，fetch/XHR 加载 .moc3 等模型文件会被
Chromium 的同源策略拦截。这里在 127.0.0.1 上起一个只读的临时 HTTP 服务，
让 Live2D 页面和模型资源走正常的 http:// 同源加载。
"""

from __future__ import annotations

import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return


class AssetServer:
    def __init__(self, root: Path) -> None:
        self._root = root
        handler = partial(_QuietHandler, directory=str(root))
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._httpd.daemon_threads = True
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, name="asset-server", daemon=True
        )
        self._thread.start()

    @property
    def base_url(self) -> str:
        host, port = self._httpd.server_address[:2]
        return f"http://{host}:{port}"

    def url(self, relative: str) -> str:
        return f"{self.base_url}/{relative.lstrip('/').replace(chr(92), '/')}"

    def shutdown(self) -> None:
        try:
            self._httpd.shutdown()
        finally:
            self._httpd.server_close()
