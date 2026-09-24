#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`capture.py` 的判据自检 —— 不编译、不截图、不需要真实版本区：

    python batch-screenshot-submit/scripts/test_capture.py

覆盖四处「错了也看不出来」的判据（正是它们容易静默失效）：

  · 空白图判定：纯色/极小图必报，有内容的图必放行
  · 字体字形判定：缺 CJK 字形的字体会被识别出来，纯 ASCII 输出不受影响
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

        # ── 字体字形：乱码（豆腐块）**不会**被空白检查拦下，必须单独判 ──
        #
        # 这就是本技能曾经的实际缺陷：Consolas 没有中文字形，中文全渲染成
        # .notdef 方框，而豆腐块图的像素标准差约 28 —— 轻松通过 check_not_blank，
        # 缺陷静默交付。下面先钉住「探针能认出缺字形的字体」，再钉住「选字体会避开它」。
        from PIL import ImageFont, ImageDraw

        # 参照字体：PIL 内置位图字体，确定不含 CJK 字形。
        bare = ImageFont.load_default()
        assert C.missing_glyphs(bare, "宝马汽车下线"), \
            "内置位图字体没有中文字形，探针必须报出来"
        assert C.missing_glyphs(bare, "BMW-3 x86_64") == set(), \
            "纯 ASCII 不该被报成缺字形"
        # 空白与零宽字符天然没有字形，不该算缺失（否则整张图都会被判不可渲染）。
        assert C.missing_glyphs(bare, " \t\n") == set()
        assert C.missing_glyphs(bare, "​﻿") == set()

        # 纯 ASCII 输出必须能选到字体 —— 与输出语言无关，任何机器上都该成立。
        font, name, problems = C.pick_console_font("$ java Main\nhello 123")
        assert font is not None, f"纯 ASCII 应能选到字体：{problems}"
        assert C.missing_glyphs(font, "$ java Main\nhello 123") == set(), name

        # 含中文的输出：要么选出能画全的字体，要么明确报错（而不是静默出豆腐块）。
        cjk = "$ java CarMain\n宝马汽车下线\n奔驰汽车下线"
        font, name, problems = C.pick_console_font(cjk)
        if font is None:
            assert problems, "选不到字体时必须给出试过哪些、各自缺什么"
        else:
            assert C.missing_glyphs(font, cjk) == set(), \
                f"选中的 {name} 仍画不出中文，等于换了个豆腐块"
            # 端到端：真的渲染一张图出来，且该图能过空白检查。
            # 注意这一步**不足以**发现乱码 —— 豆腐块图有内容、标准差约 28，
            # check_not_blank 照样放行。拦住乱码的是上面的 missing_glyphs 判据。
            out_png = d / "cjk.png"
            assert C.render_console_png(cjk, "", "CarMain", out_png) == []
            assert C.check_not_blank(out_png) == [], "渲染出的图不该是空白"

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

        # JDK 版本解析：`javac -version` 的实际输出没有引号，且旧版是 1.8 形式。
        # 解析错 → 版本闸形同虚设（比对永远拿到 None）。
        assert C._feature_of("javac 21.0.11") == 21, C._feature_of("javac 21.0.11")
        assert C._feature_of("javac 1.8.0_401") == 8, C._feature_of("javac 1.8.0_401")
        assert C._feature_of('openjdk version "17.0.2" 2022-01-18') == 17
        assert C._feature_of("javac 8") == 8
        assert C._feature_of("没版本号") is None

        # release 参数：`--release` 是 JDK 9 才有的，JDK 8 上会报「无效的标记」，
        # 所以 8 及以下必须退化成 -source/-target。退化错 → JDK 8 下编译直接失败。
        assert C.release_flags(8) == ["-source", "8", "-target", "8"], C.release_flags(8)
        assert C.release_flags(21) == ["--release", "21"], C.release_flags(21)
        assert C.release_flags(None) == [], C.release_flags(None)

        # 辅助类缓存目录必须带目标版本：不带的话 JDK 21 编的 class 会被 JDK 8
        # 运行复用，报 UnsupportedClassVersionError（看着像被测程序的错）。
        h8 = C.ensure_helper(d, "javac", 8)
        h21 = C.ensure_helper(d, "javac", 21)
        assert h8 != h21, "辅助类缓存目录没按目标版本隔离"

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
