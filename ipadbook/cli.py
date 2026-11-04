# -*- coding: utf-8 -*-
"""命令行入口：split / web

这个项目只做一件事：把整本 PDF 按章节切开，导出成 iPad 笔记 App 能直接吃的 PDF。
跟 Windows 桌面版 OneNote 打交道的代码不在这里。
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

from . import __version__


def _log(msg="", **_kw):
    """识别/切分流程会带 flush=True 调它，所以必须能吞掉额外关键字参数
    （否则第二页都还没开始就 TypeError）。"""
    print(msg, flush=True)


def cmd_split(a):
    from . import toc, splitter

    pdf = str(Path(a.pdf).resolve())
    if not Path(pdf).is_file():
        _log(f"文件不存在：{pdf}")
        return 1

    import pymupdf
    with pymupdf.open(pdf) as doc:
        total = doc.page_count
    _log(f"《{Path(pdf).stem}》 共 {total} 页，识别章节中…")

    entries, strategy = toc.build_plan(
        pdf, max_level=a.level, ocr=not a.no_ocr, every=a.every,
        toc_scan=a.toc_scan, workers=getattr(a, "ocr_workers", 1),
        front=not getattr(a, "no_front", False),
        ocr_dpi=getattr(a, "ocr_dpi", 130),
        ocr_cache=not getattr(a, "no_ocr_cache", False), log=_log,
    )
    _log(f"识别方式：{strategy}，得到 {len(entries)} 个条目")

    if getattr(a, "dry_run", False):
        for e in entries:
            _log(f"  [L{e.level}] {e.title}  -> PDF p{e.page}")
        return 0

    out = Path(a.out).resolve() if a.out else Path(pdf).parent / f"{Path(pdf).stem}_章节"
    files = splitter.split_pdf(pdf, entries, out, log=_log)
    _log(f"\n完成：{len(files)} 个文件 -> {out}")

    if getattr(a, "whole", False):
        splitter.rebuild_toc(pdf, entries, out / "_整本带目录.pdf", log=_log)
    if getattr(a, "zip", False):
        splitter.pack_zip(out, out.parent / f"{out.name}.zip", log=_log)
    return 0


def cmd_web(a):
    """启动本机 Web 服务，浏览器里用图形界面（真跑识别与切分）。"""
    from . import webui
    webui.serve(host=a.host, port=a.port, open_browser=not a.no_browser)
    return 0


def _add_split_args(s):
    s.add_argument("--level", type=int, default=1, choices=[1, 2],
                   help="1=按章（默认），2=按章+节")
    s.add_argument("--out", default="", help="输出目录，默认 <PDF名>_章节")
    s.add_argument("--every", type=int, default=30, help="识别失败时的兜底切分页数")
    s.add_argument("--toc-scan", type=int, default=30, help="扫描前 N 页找目录")
    s.add_argument("--ocr-workers", type=int, default=1, help="OCR 并行线程数，1 = 单线程（默认）")
    s.add_argument("--ocr-dpi", type=int, default=130,
                   help="OCR 渲染分辨率，默认 130；调低更快但小字可能认不出")
    s.add_argument("--no-ocr-cache", action="store_true",
                   help="不复用 OCR 缓存（默认会缓存每页识别结果，第二次识别秒过）")
    s.add_argument("--no-ocr", action="store_true", help="禁用 OCR 识别")
    s.add_argument("--no-front", action="store_true",
                   help="不单独产出前置页（封面/版权/目录）")
    s.add_argument("--whole", action="store_true",
                   help="额外导出「整本 PDF + 正确书签目录」，适合 Noteful / GoodNotes")
    s.add_argument("--zip", action="store_true",
                   help="把输出目录打包成 zip，方便一次传到 iPad")


def build_parser():
    p = argparse.ArgumentParser(
        prog="ipadbook",
        description="把整本 PDF 按章节切好，导出给 iPad 的笔记 App",
    )
    p.add_argument("--version", action="version", version=f"ipadbook {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("split", help="按章节拆分 PDF（可同时导出整本带目录 / zip）")
    s.add_argument("pdf")
    _add_split_args(s)
    s.add_argument("--dry-run", action="store_true", help="只打印结果，不切文件")
    s.set_defaults(func=cmd_split)

    w = sub.add_parser("web", help="启动本机图形界面（浏览器里拖 PDF 就切分）")
    w.add_argument("--host", default="127.0.0.1", help="监听地址（默认只本机）")
    w.add_argument("--port", type=int, default=8765)
    w.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    w.set_defaults(func=cmd_web)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args) or 0
    except KeyboardInterrupt:
        _log("\n已中断")
        return 130


if __name__ == "__main__":
    sys.exit(main())
