#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量编译 + 运行 + 截图 + 校验，产出可提交的 `提交/` 目录。

配套技能：`batch-screenshot-submit`。本文件是全部逻辑的唯一真源。

# 一条命令做什么

    python capture.py <仓库根>                     # 全部 poly-* 版本区
    python capture.py <仓库根> --area 04-FactoryPattern/poly-factory-car
    python capture.py <仓库根> --dry-run           # 只列计划，不编译不截图

对每个版本区 `<项目>/poly-<实验>/` 的每个 `vNN`：

  0. 跑 `poly-version-generator/scripts/check_code.py`（可 `--skip-check` 关）——
     编译不过、类名冲突、out 污染时**整体中止**，不产出半个提交包。
  1. 识别源根：优先 `vNN/src/`；没有则退回 `vNN/`（旧布局如 poly-singleton-demo）。
  2. 编译到 `<仓库根>/out/shot-<项目>-<区名>-<版本>/`（**每版一个独立 out**，
     绝不复用；与 poly-version-generator 的约定一致）。
  3. 运行并截图：
     · 控制台程序（源文件里无 javax.swing/java.awt）—— 捕获 stdout，用 PIL 渲染成图。
     · GUI 程序（Swing）—— 注入 `ScreenshotHelper`（编译到独立目录、**不写进 src/**），
       反射调用原 `main`，等窗口出现后 `Robot` 截窗口区域，截完退出。
  4. 校验截图不是纯色/空白（均值与方差阈值）。空白 = 该版 FAIL，整体中止。
  5. 打包 `src/**` 成 zip（含 img/ 等资源），与截图一起放进
     `<仓库根>/提交/<项目>/<区名>/`。

# 为什么这么设计

· **一版 = 一个 out 目录 = 一个工作目录**。多版常复用同名包与默认包 `Main`，
  共用 out 或共用 cwd 时 javac/java 会挑错类，或从兄弟版本拉错实现。
· **GUI 辅助类不进 src/**：`source-snapshot` 类版本区禁止改快照源码，
  辅助类编到 `out/` 下的独立目录，用 `-cp` 挂上去。
· **资源靠 classpath**：PlanWar 的 `AssetLoader` 先查 `classpath:/img/`，
  所以运行时 `-cp` 必须含 `src`（资源在那里），且 cwd 设为版本根作为回退。
· **截图必须校验非纯色**：资源没加载时 Swing 窗口是纯黑/纯白，
  不校验就会把一张空图当成成功交付。

退出码：0 = 全部成功；1 = 有失败（此时**不产出/不更新提交目录**）。
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

# ── 可调常量 ─────────────────────────────────────────────────────────
# 启动后等多久再截图：要等 JVM 起来、资源加载完、首帧画出来。
GUI_WARMUP_SECONDS = 6.0
# 截图后等多久让进程自己退出，超时则强杀。
GUI_EXIT_GRACE_SECONDS = 2.0
# 进程总超时（控制台程序应当秒退；GUI 截完就该退）。
RUN_TIMEOUT_SECONDS = 60.0
# 控制台渲染图尺寸与字体。
CONSOLE_IMAGE_SIZE = (1280, 720)
CONSOLE_FONT_SIZE = 16
CONSOLE_BG = (30, 30, 30)
CONSOLE_FG = (220, 220, 220)
CONSOLE_MAX_LINES = 34          # 720px / (16px * 1.3) 行高
# 判「不是纯色」的阈值：像素标准差低于此值视为空白图。
BLANK_STDDEV_THRESHOLD = 3.0

SUBMISSION_DIR = "提交"

def _setup_stdout() -> None:
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

def _posix(p: str | Path) -> str:
    return Path(p).as_posix()

# ── 版本区发现 ───────────────────────────────────────────────────────

def find_areas(repo_root: Path) -> list[Path]:
    """仓库根下所有 `<项目>/poly-*/` 版本区（两层深，与现有目录形状一致）。"""
    out: list[Path] = []
    for proj in sorted(repo_root.iterdir()):
        if not proj.is_dir() or proj.name.startswith(".") or proj.name == SUBMISSION_DIR:
            continue
        for area in sorted(proj.iterdir()):
            if area.is_dir() and area.name.startswith("poly-"):
                out.append(area)
    return out

def find_versions(area: Path) -> list[Path]:
    return sorted(p for p in area.iterdir()
                  if p.is_dir() and re.fullmatch(r"v\d+", p.name))

def source_root(version_dir: Path) -> tuple[Path, bool]:
    """版本里的源根。返回 (源根, 是否有独立 src/)。

    优先 `vNN/src/`；没有则退回 `vNN/` —— 旧布局（如 `poly-singleton-demo`
    直接把 `vNN/*.java` 放版本根）没有 `src/`，技能禁止改快照区，故不迁移、只兼容。
    """
    src = version_dir / "src"
    if src.is_dir():
        return src, True
    return version_dir, False

# ── JDK 选择 ────────────────────────────────────────────────────────
#
# 为什么必须先问 JDK 版本：`javac` 默认拿 PATH 上那个，而一台机器上常装好几个。
# 跑错版本的后果是**静默的**：
#   · 用高版本 JDK 编低版本目标的源码 → 编出来的 class 在目标机跑不了，
#     而在本机一切正常，直到交上去才炸。
#   · 用低版本编用了新语法的源码 → 报一堆看不懂的语法错误，看上去像源码有问题。
# 所以编译前把版本问清楚，并用 `--release` 钉住，而不是靠 PATH 上碰巧是哪个。

# javac 的版本行有两种写法：`javac 21.0.11`（现代）与 `javac 1.8.0_401`（旧）。
# 都取主版本：21 / 8。别要求带引号 —— 实测输出里没有。
def _feature_of(text: str) -> int | None:
    """从 `javac 21.0.11` / `javac 1.8.0_401` 里取出主版本（21 / 8）。"""
    m = re.search(r"(\d+)\.(\d+)", text)
    if m:
        major, minor = int(m.group(1)), int(m.group(2))
        # 1.8 → 8；21.0 → 21。
        return minor if major == 1 else major
    m = re.search(r"\b(\d+)\b", text)
    return int(m.group(1)) if m else None

def probe_jdk(javac: str) -> tuple[str, int | None] | None:
    """问 `javac -version` 拿到 (版本号原文, 主版本整数)。拿不到返回 None。"""
    try:
        proc = subprocess.run([javac, "-version"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
    except OSError:
        return None
    blob = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if not blob:
        return None
    return blob.split("\n")[0], _feature_of(blob)

def resolve_jdk(args, javac: str, java: str) -> tuple[str, str, int | None, list[str]]:
    """确定用哪个 JDK 编译/运行。返回 (javac, java, release 主版本或 None, 提示行)。

    优先级：`--jdk` > `--javac`/`--java` 显式指定 > 交互式提问（仅 TTY）> PATH。
    **非交互（管道/CI）不提问**，否则脚本会卡在等输入上。
    """
    notes: list[str] = []

    if args.jdk:
        home = Path(args.jdk)
        if not home.is_dir():
            raise SystemExit(f"× --jdk 指向的不是目录：{_posix(home)}")
        javac = str(home / "bin" / ("javac.exe" if os.name == "nt" else "javac"))
        java = str(home / "bin" / ("java.exe" if os.name == "nt" else "java"))
        notes.append(f"JDK 由 --jdk 指定：{_posix(home)}")
    elif args.javac != "javac" or args.java != "java":
        notes.append(f"JDK 由 --javac/--java 指定：{javac} / {java}")
    elif args.jdk_version:
        notes.append(f"JDK 由 --jdk-version {args.jdk_version} 指定")
    elif sys.stdin.isatty() and not args.no_prompt:
        # 探测 PATH 上那个，把结果当默认值给用户确认。
        probe = probe_jdk(javac)
        default = str(probe[1]) if probe else ""
        shown = probe[0] if probe else "未检测到 javac"
        prompt = f"用哪个 JDK 编译/运行？（当前 PATH 上：{shown}）"
        if default:
            prompt += f"［回车 = {default}］"
        prompt += "："
        try:
            ans = input(prompt).strip()
        except EOFError:
            # EOF（stdin 是管道、没人答）不该当成取消：用探测到的默认值继续。
            print()
            ans = default
        except KeyboardInterrupt:
            # Ctrl+C 是人主动要停，那就真停。
            print()
            raise SystemExit("× 已取消")
        if not ans:
            ans = default
        if not ans:
            raise SystemExit(
                "× 没拿到 JDK 版本，PATH 上也没有 javac。"
                "用 --jdk <JDK_HOME> 指定，或先装 JDK。")
        args.jdk_version = ans
    else:
        notes.append("非交互模式：JDK 用 PATH 上的 javac/java（要钉版本请传 --jdk 或 --jdk-version）")

    release = None
    if args.jdk_version:
        m = re.fullmatch(r"(?:1\.)?(\d+)", args.jdk_version.strip())
        if not m:
            raise SystemExit(f"× 认不出 JDK 版本：{args.jdk_version}（要的是主版本号，如 21）")
        release = int(m.group(1))

    # 钉住的版本与实际编译器不一致时报警：`--release 21` 用 JDK 17 编不出来。
    probe = probe_jdk(javac)
    if probe is None:
        notes.append(f"⚠ 跑不了 `{javac} -version`，无法核对版本")
    else:
        actual = probe[1]
        if release is not None and actual is not None and release > actual:
            raise SystemExit(
                f"× 指定的 JDK {release} 高于实际编译器 {actual}（{probe[0]}）。"
                f"换 --jdk <JDK_HOME> 指向装了 JDK {release} 的目录。")
        notes.append(f"实际编译器：{probe[0]}")
        if release is not None:
            notes.append(f"目标版本：--release {release}")

    return javac, java, release, notes

# ── 程序类型判定 ─────────────────────────────────────────────────────

GUI_MARKERS = ("javax.swing", "java.awt.Graphics", "extends JFrame", "extends JPanel")

def _java_files(root: Path) -> list[Path]:
    return [p for p in sorted(root.rglob("*.java")) if p.is_file()]

def is_gui(java_files: list[Path]) -> bool:
    for p in java_files:
        txt = p.read_text(encoding="utf-8", errors="replace")
        if any(m in txt for m in GUI_MARKERS):
            return True
    return False

def find_main_class(java_files: list[Path]) -> str | None:
    """含 `static void main` 的类的全限定名；有多个时取最短路径的那个。"""
    hits: list[tuple[int, str]] = []
    for p in java_files:
        txt = p.read_text(encoding="utf-8", errors="replace")
        if "static void main" not in txt:
            continue
        m = re.search(r"^\s*package\s+([\w.]+)\s*;", txt, re.M)
        cls = re.search(r"^\s*(?:public\s+)?(?:final\s+)?class\s+(\w+)", txt, re.M)
        if not cls:
            continue
        name = f"{m.group(1)}.{cls.group(1)}" if m else cls.group(1)
        hits.append((len(p.parts), name))
    if not hits:
        return None
    return sorted(hits)[0][1]

# ── 编译 ─────────────────────────────────────────────────────────────

def compile_version(src_root: Path, out_dir: Path, extra_src: Path | None,
                    javac: str, release: int | None = None) -> list[str]:
    """整套编译到本版专属 out。绝不只编入口。"""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = [str(p) for p in _java_files(src_root)]
    cmd = [javac, "-encoding", "UTF-8", "-implicit:none",
           "-sourcepath", str(src_root)]
    if release is not None:
        # 钉住目标版本："1.8" 与 "8" 是同一个意思，javac 两种都收。
        cmd += ["--release", str(release)]
    if extra_src is not None:
        # 辅助类另编一份，只加 classpath，不进 -sourcepath（否则会被当源码打包）
        cmd += ["-cp", str(extra_src)]
    cmd += ["-d", str(out_dir), *files]
    proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().replace("\\", "/")
        return [f"编译失败：\n{detail}"]
    return []

# ── GUI 截图辅助类 ───────────────────────────────────────────────────
#
# 为什么是注入一个类而不是外部全屏截图：窗口坐标只有进程内知道。外部截图还依赖
# 「窗口在前台、无遮挡」，切个窗口或 CI 里跑就废。这里用 Robot 截已知 bounds。

SCREENSHOT_HELPER_SRC = r'''
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.File;
import java.lang.reflect.Method;
import javax.imageio.ImageIO;

/** 截图助手：反射调用原 main，等窗口出现后截窗口区域。不修改被测程序一行。 */
public final class ScreenshotHelper {
    public static void main(String[] args) throws Exception {
        String mainClass = args[0];
        String outPath = args[1];
        long warmupMs = Long.parseLong(args[2]);

        Thread app = new Thread(() -> {
            try {
                Method m = Class.forName(mainClass).getMethod("main", String[].class);
                m.invoke(null, (Object) new String[0]);
            } catch (Throwable t) {
                System.err.println("__APP_ERROR__ " + t);
            }
        }, "app");
        app.setDaemon(true);
        app.start();

        // 等窗口出现（而不是死等固定时长）：最多 warmupMs，每 200ms 探一次。
        long deadline = System.currentTimeMillis() + warmupMs;
        Window target = null;
        while (System.currentTimeMillis() < deadline) {
            Thread.sleep(200);
            for (Window w : Window.getWindows()) {
                if (w.isShowing() && w.getWidth() > 50 && w.getHeight() > 50) {
                    target = w;
                    break;
                }
            }
            if (target != null) break;
        }
        if (target == null) {
            System.err.println("__NO_WINDOW__");
            System.exit(3);
        }

        // 首帧可能刚画完，再给一点时间把画面稳定下来。
        Thread.sleep(1200);

        Rectangle b = target.getBounds();
        BufferedImage img = new Robot().createScreenCapture(b);
        ImageIO.write(img, "png", new File(outPath));
        System.out.println("__SHOT_OK__ " + b.width + "x" + b.height);
        System.exit(0);
    }
}
'''

def ensure_helper(out_root: Path, javac: str, release: int | None = None) -> Path:
    """把 ScreenshotHelper 编到 out_root/_helper/，返回该目录。已存在则复用。"""
    helper_dir = out_root / "_helper"
    marker = helper_dir / "ScreenshotHelper.class"
    if marker.is_file():
        return helper_dir
    helper_dir.mkdir(parents=True, exist_ok=True)
    src = helper_dir / "ScreenshotHelper.java"
    src.write_text(SCREENSHOT_HELPER_SRC, encoding="utf-8")
    cmd = [javac, "-encoding", "UTF-8"]
    if release is not None:
        # 辅助类必须与主代码同目标版本：编成高版本会让低版 JRE 连截图都跑不起来。
        cmd += ["--release", str(release)]
    cmd += ["-d", str(helper_dir), str(src)]
    proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if proc.returncode != 0:
        raise SystemExit("× 截图辅助类编译失败：\n" + (proc.stderr or proc.stdout))
    return helper_dir

# ── 运行与截图 ───────────────────────────────────────────────────────

def run_console(java: str, src_root: Path, out_dir: Path, main_class: str,
                cwd: Path) -> tuple[str, str]:
    """跑控制台程序，返回 (stdout, stderr)。"""
    cmd = [java, "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8",
           "-cp", os.pathsep.join([str(out_dir), str(src_root)]), main_class]
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=str(cwd),
                          timeout=RUN_TIMEOUT_SECONDS)
    return proc.stdout or "", proc.stderr or ""

def run_gui_shot(java: str, src_root: Path, out_dir: Path, helper_dir: Path,
                 main_class: str, png: Path, cwd: Path) -> list[str]:
    """跑 GUI 程序并截窗口图。返回问题列表（空 = 成功）。"""
    cmd = [java, "-Djava.awt.headless=false", "-Dfile.encoding=UTF-8",
           "-Dstdout.encoding=UTF-8",
           "-cp", os.pathsep.join([str(out_dir), str(helper_dir), str(src_root)]),
           "ScreenshotHelper", main_class, str(png), str(int(GUI_WARMUP_SECONDS * 1000))]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", cwd=str(cwd),
                              timeout=RUN_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return [f"GUI 进程超时（{RUN_TIMEOUT_SECONDS:.0f}s 未退出）"]
    err = (proc.stderr or "") + (proc.stdout or "")
    if "__NO_WINDOW__" in err:
        return ["找不到可见窗口（程序没起来或窗口未显示）—— 若在无桌面环境运行，"
                "确认已加 -Djava.awt.headless=false 且有可用显示"]
    if "__APP_ERROR__" in err:
        line = [l for l in err.split("\n") if "__APP_ERROR__" in l][0]
        return [f"被测程序运行抛异常：{line.strip()}"]
    if proc.returncode != 0 or not png.is_file():
        return [f"截图失败（退出码 {proc.returncode}）：{err.strip()[:400]}"]
    return []

def render_console_png(stdout: str, stderr: str, main_class: str, png: Path) -> None:
    """把控制台输出渲染成图。不放真终端截图 —— 那受字体/尺寸/主题影响，不可复现。"""
    from PIL import Image, ImageDraw, ImageFont

    lines = [f"$ java {main_class}"]
    lines += stdout.rstrip("\n").split("\n") if stdout.strip() else ["(无输出)"]
    if stderr.strip():
        lines.append("")
        lines += ["[stderr] " + l for l in stderr.rstrip("\n").split("\n")]
    if len(lines) > CONSOLE_MAX_LINES:
        lines = lines[:CONSOLE_MAX_LINES] + [f"... (共 {len(lines)} 行)"]

    img = Image.new("RGB", CONSOLE_IMAGE_SIZE, CONSOLE_BG)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("consola.ttf", CONSOLE_FONT_SIZE)
    except OSError:
        try:
            font = ImageFont.truetype("cour.ttf", CONSOLE_FONT_SIZE)
        except OSError:
            font = ImageFont.load_default()

    y = 18
    for line in lines:
        draw.text((18, y), line, fill=CONSOLE_FG, font=font)
        y += int(CONSOLE_FONT_SIZE * 1.35)
    img.save(png)

def check_not_blank(png: Path) -> list[str]:
    """截出来是一张纯色/空白图 = 资源没加载、窗口没画出来。

    必须校验：不校验就会把一张黑图当成成功交付。窗口尺寸也可能异常（0 宽）。
    """
    from PIL import Image, ImageStat
    with Image.open(png) as im:
        im = im.convert("RGB")
        w, h = im.size
        if w < 50 or h < 50:
            return [f"截图尺寸异常（{w}x{h}）"]
        stat = ImageStat.Stat(im)
        stdev = sum(stat.stddev) / 3.0
        if stdev < BLANK_STDDEV_THRESHOLD:
            mean = tuple(round(v) for v in stat.mean)
            return [f"截图是纯色/空白（均值 {mean}，标准差 {stdev:.2f}）—— "
                    f"多半是资源没加载（确认 -cp 含 src/、cwd 为版本根）"]
    return []

# ── 打包与归位 ───────────────────────────────────────────────────────

def pack_src_zip(src_root: Path, zip_path: Path, keep_root_name: str) -> None:
    """把 src/** 全打（含 img/、.wav）。只打 .java 的包运行不了。"""
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(src_root.rglob("*")):
            if p.is_file():
                zf.write(p, arcname=str(Path(keep_root_name) / p.relative_to(src_root)))
        if not any(True for _ in src_root.rglob("*")):
            zf.writestr(f"{keep_root_name}/.keep", "")

def run_check_code(repo_root: Path, area: Path, checks_script: Path | None,
                   python: str, out_root: Path, javac: str) -> list[str]:
    """跑 poly-version-generator 的 check_code.py（存在才跑）。

    **给每个版本区一个专属 out 根**（`out/check-<项目>-<区名>/`）：
    `check_code.py` 的路径形状是 `<out-root>/<vNN>/`，而各区的版本名都是
    `v01`…`v05`。若共用一个 out 根，A 区的 `out/v01` 会被 B 区的检查当成
    「本版 out 里出现了源码之外的类」—— 假阳性，且正好掩盖真实的污染。
    """
    if checks_script is None or not checks_script.is_file():
        return []
    area_out = out_root / f"check-{area.parent.name}-{area.name}"
    proc = subprocess.run([python, str(checks_script), str(area),
                           "--out-root", str(area_out), "--javac", javac],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    if proc.returncode != 0:
        return ["代码检查（check_code.py）未通过：\n" + (proc.stdout or "").strip()]
    return []

# ── 主流程 ───────────────────────────────────────────────────────────

def process_area(repo_root: Path, area: Path, sub_root: Path, out_root: Path,
                 javac: str, java: str, python: str, checks_script: Path | None,
                 skip_check: bool, dry_run: bool, release: int | None = None) -> list[str]:
    proj = area.parent.name
    area_name = area.name
    problems: list[str] = []

    versions = find_versions(area)
    if not versions:
        return [f"{_posix(area.relative_to(repo_root))} 下没有 vNN 版本目录"]

    if not skip_check and not dry_run:
        problems += run_check_code(repo_root, area, checks_script, python, out_root, javac)
        if problems:
            return problems

    stage = out_root / f"stage-{proj}-{area_name}"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True, exist_ok=True)

    helper_dir = ensure_helper(out_root, javac, release) if not dry_run else out_root / "_helper"

    for v in versions:
        src_root, has_src = source_root(v)
        files = _java_files(src_root)
        if not files:
            problems.append(f"{v.name}：{_posix(src_root)} 下没有源文件")
            continue
        gui = is_gui(files)
        main_class = find_main_class(files)
        if main_class is None:
            problems.append(f"{v.name}：找不到含 static void main 的类")
            continue

        if dry_run:
            kind = "GUI" if gui else "控制台"
            extra = "" if has_src else "（旧布局，源根 = 版本根）"
            print(f"    · {v.name}  {kind:<4}  main={main_class}  "
                  f"文件={len(files)}{extra}")
            continue

        out_dir = out_root / f"shot-{proj}-{area_name}-{v.name}"
        errs = compile_version(src_root, out_dir, helper_dir if gui else None, javac, release)
        if errs:
            problems += [f"{v.name}：{e}" for e in errs]
            continue

        png = stage / f"{v.name}.png"
        # cwd = 版本根：AssetLoader 的第二条回退路径是 `src/img/`，相对版本根。
        cwd = v
        if gui:
            errs = run_gui_shot(java, src_root, out_dir, helper_dir, main_class,
                                png, cwd)
        else:
            try:
                out, serr = run_console(java, src_root, out_dir, main_class, cwd)
            except subprocess.TimeoutExpired:
                errs = [f"运行超时（{RUN_TIMEOUT_SECONDS:.0f}s）—— 控制台程序应当秒退"]
            else:
                errs = []
                if serr.strip() and "Exception" in serr:
                    errs = [f"运行期报错：{serr.strip()[:300]}"]
                else:
                    render_console_png(out, serr, main_class, png)
        if errs:
            problems += [f"{v.name}：{e}" for e in errs]
            continue

        errs = check_not_blank(png)
        if errs:
            problems += [f"{v.name}：{e}" for e in errs]
            continue

        print(f"    √ {v.name}  截图 {png.stat().st_size // 1024} KB")

    if problems:
        return problems

    if dry_run:
        return []

    # ── 全部版本都过了才产出提交目录：要么完整要么没有 ──────────────
    dest = sub_root / proj / area_name
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    for v in versions:
        src_root, _ = source_root(v)
        pack_src_zip(src_root, dest / f"{v.name}-src.zip", "src")
        shutil.copy2(stage / f"{v.name}.png", dest / f"{v.name}.png")

    shutil.rmtree(stage, ignore_errors=True)
    rel = _posix(dest.relative_to(repo_root))
    print(f"  → {rel}/  {len(list(dest.iterdir()))} 个文件")
    return []

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="capture.py",
        description="批量编译、运行、截图并打包成 提交/ 目录。",
    )
    ap.add_argument("repo_root", type=Path,
                    help="仓库根，如 C:/workspace/class/DesignPatterns")
    ap.add_argument("--area", action="append", default=None,
                    help="只处理指定版本区（相对仓库根，可重复），如 04-FactoryPattern/poly-factory-car")
    ap.add_argument("--dry-run", action="store_true", help="只列计划，不编译不截图")
    ap.add_argument("--skip-check", action="store_true",
                    help="跳过 poly-version-generator 的 check_code.py 前置检查")
    ap.add_argument("--out-root", type=Path, default=None,
                    help="编译输出根（默认 <仓库根>/out）")
    ap.add_argument("--submission-root", type=Path, default=None,
                    help=f"提交目录根（默认 <仓库根>/{SUBMISSION_DIR}）")
    ap.add_argument("--javac", default="javac")
    ap.add_argument("--java", default="java")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--jdk", default=None,
                    help="JDK_HOME 目录（含 bin/javac）。指定后不再提问，优先于 --javac/--java")
    ap.add_argument("--jdk-version", default=None,
                    help="目标主版本号，如 21；传给 javac 的 --release，并校验不高于实际编译器")
    ap.add_argument("--no-prompt", action="store_true",
                    help="即使交互也不提问 JDK 版本（脚本/CI 用）")
    args = ap.parse_args(argv)

    _setup_stdout()

    repo_root: Path = args.repo_root
    if not repo_root.is_dir():
        print(f"× 仓库根不存在：{_posix(repo_root)}")
        return 1

    sub_root = args.submission_root or (repo_root / SUBMISSION_DIR)
    out_root = args.out_root or (repo_root / "out")
    try:
        out_root.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"× 建不出编译输出目录 {_posix(out_root)}：{e}")
        return 1

    if args.area:
        areas = [(repo_root / a) for a in args.area]
        missing = [a for a in areas if not a.is_dir()]
        if missing:
            print("× 版本区不存在：" + "、".join(_posix(m) for m in missing))
            return 1
    else:
        areas = find_areas(repo_root)
    if not areas:
        print(f"× {_posix(repo_root)} 下没找到 <项目>/poly-*/ 版本区")
        return 1

    # check_code.py 优先用仓库自带的，其次找 DesignPatterns 里装的技能副本。
    checks = repo_root / "skills/code/poly-version-generator/scripts/check_code.py"
    if not checks.is_file():
        for cand in (repo_root / ".claude/skills/poly-version-generator/scripts/check_code.py",
                     repo_root / ".agents/skills/poly-version-generator/scripts/check_code.py"):
            if cand.is_file():
                checks = cand
                break
        else:
            checks = None

    print(f"仓库：{_posix(repo_root)}")
    # JDK 选择必须在跑 check_code.py 之前定下来：它也带一套 javac，
    # 两边用不同版本会出现「检查过了、正式编译却失败」这种自相矛盾的结果。
    javac, java, release, jdk_notes = resolve_jdk(args, args.javac, args.java)
    print(f"提交目录：{_posix(sub_root)}/")
    print(f"编译输出：{_posix(out_root)}/（每版独立目录，绝不复用）")
    for n in jdk_notes:
        print(f"JDK：{n}")
    print(f"前置检查：{'check_code.py' if checks and not args.skip_check else '跳过'}")
    print(f"版本区：{len(areas)} 个" + ("（dry-run）" if args.dry_run else ""))
    print()

    failed = 0
    for area in areas:
        rel = _posix(area.relative_to(repo_root)) if area.is_relative_to(repo_root) else _posix(area)
        print(f"== {rel}")
        problems = process_area(repo_root, area, sub_root, out_root,
                               javac, java, args.python, checks,
                               args.skip_check, args.dry_run, release)
        if problems:
            failed += 1
            print(f"  × FAIL")
            for p in problems:
                for i, line in enumerate(p.split("\n")):
                    print(f"      {line}" if i == 0 else f"        {line}")
        print()

    if failed:
        print(f"× {failed}/{len(areas)} 个版本区失败 —— 未产出（或未更新）提交目录")
        print("  提交包要么完整要么没有：一个残缺的提交包比没有更糟。")
        return 1
    if args.dry_run:
        print("√ dry-run 完成（未产出任何文件）")
        return 0
    print(f"√ {len(areas)}/{len(areas)} 个版本区完成 —— 提交目录在 {_posix(sub_root)}/")
    return 0

if __name__ == "__main__":
    sys.exit(main())
