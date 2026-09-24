#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`capture.py` 的判据自检 —— 不编译、不截图、不需要真实版本区：

    python batch-screenshot-submit/scripts/test_capture.py

覆盖三处「错了也看不出来」的判据（正是它们容易静默失效）：

  · 空白图判定：纯色/极小图必报，有内容的图必放行
  · 程序类型判定：Swing 源码判 GUI，纯控制台判非 GUI
  · 源根识别：有 `src/` 用 `src/`，旧布局退回版本根
  · zip 打包：源码与二进制资源都在包里，且路径前缀是 `src/`

退出码 0 = 全通过；1 = 有断言失败（脚本有问题，不是被检对象有问题）。
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capture as C          # noqa: E402

from PIL import Image        # noqa: E402

def _flat(path: Path, color: tuple[int, int, int], size=(500, 400)) -> None:
    Image.new("RGB", size, color).save(path)

def _textured(path: Path) -> None:
    im = Image.new("RGB", (500, 400), (0, 0, 0))
    for x in range(0, 500, 3):
        for y in range(0, 400, 3):
            if (x + y) % 7 < 3:
                im.putpixel((x, y), (255, 255, 255))
    im.save(path)

def main() -> int:
    d = Path(tempfile.mkdtemp())
    try:
        # 空白图：纯黑窗口 = 资源没加载。必须报，否则空图被当成功交付。
        blank = d / "blank.png"
        _flat(blank, (0, 0, 0))
        assert C.check_not_blank(blank), "纯色图应被判空白"

        # 极小图：窗口尺寸异常（0 宽之类）也要拦。
        tiny = d / "tiny.png"
        Image.new("RGB", (10, 10), (255, 255, 255)).save(tiny)
        assert C.check_not_blank(tiny), "过小的图应被拦"

        # 有内容的图：放行。阈值定得过松会把这种图也拦掉。
        good = d / "good.png"
        _textured(good)
        assert C.check_not_blank(good) == [], C.check_not_blank(good)

        # 程序类型：含 swing/awt 的判 GUI，纯控制台的判非 GUI。
        gui_dir = d / "gui"
        gui_dir.mkdir()
        (gui_dir / "Main.java").write_text(
            "import javax.swing.JFrame;\npublic class Main {}\n", encoding="utf-8")
        assert C.is_gui(C._java_files(gui_dir)), "含 swing 应判 GUI"

        cli_dir = d / "cli"
        cli_dir.mkdir()
        (cli_dir / "Main.java").write_text(
            "public class Main { public static void main(String[] a){} }\n", encoding="utf-8")
        assert not C.is_gui(C._java_files(cli_dir)), "纯控制台不该判 GUI"

        # 入口类：带包名的要出全限定名，否则 java -cp 起不来。
        (cli_dir / "PkgMain.java").write_text(
            "package p.q;\npublic class PkgMain { public static void main(String[] a){} }\n",
            encoding="utf-8")
        assert C.find_main_class(C._java_files(cli_dir)) == "Main", \
            C.find_main_class(C._java_files(cli_dir))
        assert C.find_main_class(C._java_files(gui_dir)) is None

        # 源根：有 src/ 用它；旧布局退回版本根。
        v_new = d / "area" / "v01"
        (v_new / "src").mkdir(parents=True)
        assert C.source_root(v_new) == (v_new / "src", True)
        v_old = d / "area" / "v02"
        v_old.mkdir(parents=True)
        assert C.source_root(v_old) == (v_old, False)

        # 打包：源码与二进制资源都要在包里（只打 .java 的包跑不起来）。
        src_root = d / "packsrc"
        (src_root / "a").mkdir(parents=True)
        (src_root / "a" / "Main.java").write_text("public class Main {}\n", encoding="utf-8")
        (src_root / "img").mkdir()
        (src_root / "img" / "h.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
        zp = d / "v01-src.zip"
        C.pack_src_zip(src_root, zp, "src")
        names = set(zipfile.ZipFile(zp).namelist())
        assert names == {"src/a/Main.java", "src/img/h.png"}, names
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("SELF-CHECK OK")
    return 0

if __name__ == "__main__":
    sys.exit(main())
