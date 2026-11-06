"""下载 Live2D 网页运行时与官方示例模型（Hiyori）。

用法：
    python tools/fetch_assets.py            # 运行时 + Hiyori 示例模型
    python tools/fetch_assets.py --no-model # 只下载运行时
    python tools/fetch_assets.py --force    # 覆盖已存在的文件

说明：示例模型来自 Live2D 官方 CubismWebSamples 仓库，仅用于本地开发调试，
请遵循 Live2D Cubism 示例模型许可；正式发布时请替换为你拥有授权的模型。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.parse
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "web" / "vendor"
MODELS = ROOT / "assets" / "models"

HEADERS = {"User-Agent": "MyDigitalMaid/0.1 (local development)"}

VENDOR_FILES = [
    (
        ["https://cdn.jsdelivr.net/npm/pixi.js@6.5.10/dist/browser/pixi.min.js"],
        "pixi.min.js",
    ),
    (
        ["https://cubism.live2d.com/sdk-web/cubismcore/live2dcubismcore.min.js"],
        "live2dcubismcore.min.js",
    ),
    (
        ["https://cdn.jsdelivr.net/npm/pixi-live2d-display@0.4.0/dist/cubism4.min.js"],
        "pixi-live2d-display-cubism4.min.js",
    ),
    (
        [
            "https://raw.githubusercontent.com/qt/qtwebchannel/6.6/examples/webchannel/shared/qwebchannel.js",
            "https://cdn.jsdelivr.net/gh/qt/qtwebchannel@6.6/examples/webchannel/shared/qwebchannel.js",
        ],
        "qwebchannel.js",
    ),
]

GITHUB_TREE = (
    "https://api.github.com/repos/Live2D/CubismWebSamples/git/trees/develop?recursive=1"
)
MODEL_MIRRORS = [
    "https://cdn.jsdelivr.net/gh/Live2D/CubismWebSamples@develop/",
    "https://raw.githubusercontent.com/Live2D/CubismWebSamples/develop/",
]
MODEL_PREFIX = "Samples/Resources/Hiyori/"


def download(urls: str | list[str], destination: Path, force: bool = False) -> None:
    if destination.exists() and destination.stat().st_size > 0 and not force:
        print(f"  skip  {destination.relative_to(ROOT)}")
        return

    sources = [urls] if isinstance(urls, str) else urls
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")

    last_error: Exception | None = None
    for source in sources:
        for attempt in range(2):
            try:
                request = urllib.request.Request(source, headers=HEADERS)
                with urllib.request.urlopen(request, timeout=120) as response:
                    with open(temporary, "wb") as handle:
                        shutil.copyfileobj(response, handle)
                temporary.replace(destination)
                print(f"  ok    {destination.relative_to(ROOT)}")
                return
            except Exception as exc:  # noqa: BLE001 - 逐个镜像重试
                last_error = exc
                temporary.unlink(missing_ok=True)
                if attempt == 0:
                    print(f"  retry {destination.name}: {exc}")

    raise RuntimeError(f"下载 {destination.name} 失败：{last_error}")


def fetch_runtime(force: bool) -> None:
    print("[1/2] 下载 Live2D 网页运行时")
    for urls, filename in VENDOR_FILES:
        download(urls, VENDOR / filename, force)


def fetch_hiyori(force: bool) -> None:
    print("[2/2] 下载 Hiyori 示例模型")
    request = urllib.request.Request(GITHUB_TREE, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=60) as response:
        tree = json.load(response)

    if tree.get("truncated"):
        print("  warning: GitHub 返回的目录树被截断，可能缺少部分文件")

    entries = [
        item
        for item in tree.get("tree", [])
        if item.get("type") == "blob" and item.get("path", "").startswith(MODEL_PREFIX)
    ]
    if not entries:
        raise RuntimeError("没有在 CubismWebSamples 中找到 Hiyori 模型文件")

    for index, item in enumerate(entries, start=1):
        path = item["path"]
        relative = path[len(MODEL_PREFIX) :]
        quoted = urllib.parse.quote(path, safe="/")
        urls = [mirror + quoted for mirror in MODEL_MIRRORS]
        print(f"  [{index}/{len(entries)}]")
        download(urls, MODELS / "hiyori" / relative, force)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="下载 Live2D 运行时与示例模型")
    parser.add_argument("--no-model", action="store_true", help="只下载网页运行时")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的文件")
    args = parser.parse_args(argv)

    try:
        fetch_runtime(args.force)
        if not args.no_model:
            fetch_hiyori(args.force)
    except Exception as exc:  # noqa: BLE001 - 命令行脚本直接给出错误
        print(f"下载失败：{exc}", file=sys.stderr)
        return 1

    print("完成。启动客户端即可看到 Live2D 舞台。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
