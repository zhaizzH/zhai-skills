#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""poly-version-generator 的「运行期」检查：每个 vNN 必须**独立编译通过**。

本文件是「怎么编、怎么跑」的唯一真源，与 `audit_layout.py`（只管「放在哪」）互补。

# 解决的问题

同一批版本若各写各的同名包（`model` / `service` / `controller` / `ui`），且都用默认包
的 `Main`，一旦**编进同一个 out/ 或从同一个 classpath 运行**，`java Main` 会挑错
`Main.class`、或从兄弟版本拉错 `model.Player` —— 报「找不到主类」或静默跑错版本。

这不是目录布局问题（`audit_layout.py` 的 `src/` 内部结构本就「不管」），
而是**构建方式**问题。所以规则在这里：

    一个版本 = 一个 out 目录 = 一个工作目录。绝不复用 out/。

# 检查的四类真实故障

1. **重复简单类名** —— 同一 `src/` 树内出现两个同名顶层类（`a/Main.java` 与
   `b/Main.java` 若是不同包则合法，但**同包不同文件重名**必炸）。
2. **未解析的本树 import** —— `import foo.Bar;` 但本树里没有 `foo/Bar.java`
   （外部 jar / `java.*` / `javax.*` / 通配 import 不算）。
3. **整套编译** —— `javac $(find src -name '*.java')`，**绝不只编入口**。
   只编入口时依赖不在 sourcepath → `cannot find symbol`；或运行期
   `NoClassDefFoundError`。
4. **类路径卫生** —— 编译/运行用的 out 目录必须属于本版本；若命令行里带上
   兄弟版本的 out，报出来。

# 用法

    python check_code.py poly-singleton            # 检查所有 vNN
    python check_code.py poly-singleton --only v03
    python check_code.py poly-singleton --javac "javac"   # 指定编译器

退出码：0 = 全部 PASS；1 = 有版本 FAIL（或用法/参数错误）。

依赖：仅标准库。**非 Java 项目**（`src/` 下无 `.java`）只跑 1、2 两条静态检查，
编译那两条自动跳过 —— 换语言时不改脚本，只改本文件顶部的 `SOURCE_EXTS`。
"""

from __future__ import annotations

import argparse
import ast
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

def _setup_stdout() -> None:
    """Windows GBK 控制台编不出 `⚠`/`√`：降级为 `?`，别中断整个检查。"""
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

# 参与检查的源文件后缀。换语言时改这里（`audit_layout.py` 不看代码，故不涉及）。
SOURCE_EXTS: tuple[str, ...] = (".java",)

# Java 源文件里的包声明与 import。只认行首（允许前导空白），注释里的示例不算 ——
# 不引第三方解析器，够用了。
PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.M)
IMPORT_RE = re.compile(r"^\s*import\s+(?:static\s+)?([\w.]+(?:\.\*)?)\s*;", re.M)
# 顶层类/接口/枚举/记录的声明。只认行首（允许前导空白），所以嵌套在别处的类不算 ——
# 文件名与类名不一致时（`Dup.java` 里声明 `class Main`）靠它才能发现冲突。
TYPE_RE = re.compile(r"^\s*(?:public\s+|final\s+|abstract\s+|sealed\s+|non-sealed\s+)*"
                     r"(?:class|interface|enum|record)\s+(\w+)", re.M)

# 这些前缀的 import 不是本树文件，跳过解析（JDK 自带 + 常见框架）。
NON_LOCAL_PREFIXES: tuple[str, ...] = (
    "java.", "javax.", "jdk.", "sun.", "com.sun.",
    "org.w3c.", "org.xml.", "org.ietf.",
)

# 版本根/源码树下不该出现的构建产物目录（各版本的 out 必须放**仓库根**，不放版本内）。
BUILD_DIRS: tuple[str, ...] = ("out", "bin", "target", "build", "classes")

def _posix(p: str | Path) -> str:
    return Path(p).as_posix()

def _ignored(rel: Path) -> bool:
    """与 audit_layout.py 的 IGNORE_* 保持同类：产物与 IDE 元数据不参与检查。"""
    if any(part in {"__pycache__", ".venv", ".idea", ".vscode"} for part in rel.parts):
        return True
    return rel.name.endswith((".class", ".iml", ".log", ".tmp", ".bak")) or rel.name.startswith("~$")

def find_versions(area_root: Path) -> list[Path]:
    """区里所有 `v数字` 版本目录，按名字排序。"""
    if not area_root.is_dir():
        return []
    return sorted(p for p in area_root.iterdir()
                  if p.is_dir() and re.fullmatch(r"v\d+", p.name))

def source_files(src: Path) -> list[Path]:
    """`src/` 下所有参与检查的源文件（相对 src 的路径）。"""
    if not src.is_dir():
        return []
    out: list[Path] = []
    for p in sorted(src.rglob("*")):
        if p.is_file() and not _ignored(p.relative_to(src)) and p.suffix in SOURCE_EXTS:
            out.append(p.relative_to(src))
    return out

def declared_fqn(text: str, rel: Path) -> str:
    """源文件的**主类型**全限定名：`package a.b; class Main` → `a.b.Main`。

    类名优先取文件里的顶层类型声明，取不到才退回文件名 —— 两者不一致时
    （`Dup.java` 里写 `class Main`）必须按**类名**算，否则同性冲突查不出来：
    同一 classpath 下 java 看到的是类名，不是文件名。

    没写 package（默认包）→ 不加前缀。这使「同包同名」可被检出，
    而「不同包同名」被正确放行 —— 文件 basename 重复本身不是错。
    """
    m = PACKAGE_RE.search(text)
    pkg = m.group(1) if m else ""
    t = TYPE_RE.search(text)
    name = t.group(1) if t else rel.stem
    return f"{pkg}.{name}" if pkg else name

def check_static(version_dir: Path) -> list[str]:
    """静态检查：重复全限定名 + 未解析的本树 import。不依赖 JDK。"""
    problems: list[str] = []
    src = version_dir / "src"
    files = source_files(src)
    if not files:
        return problems

    texts: dict[Path, str] = {
        rel: (src / rel).read_text(encoding="utf-8", errors="replace") for rel in files
    }

    # ── 1. 全限定名重复 ────────────────────────────────────────
    # 判据是「包声明 + 文件名」，不是 basename：`a/Main.java` 与 `b/Main.java`
    # 在不同包下**合法**，报它们就是误报。
    seen: dict[str, list[str]] = {}
    for rel, text in texts.items():
        seen.setdefault(declared_fqn(text, rel), []).append(_posix(rel))
    for fqn, claimants in sorted(seen.items()):
        if len(claimants) > 1:
            problems.append(
                f"同类名冲突：{fqn} 被 {len(claimants)} 个文件声明（{'、'.join(claimants)}）"
                " —— 同一有效 classpath 下 javac/java 会挑错那个 .class"
            )

    # ── 2. import 解析 ─────────────────────────────────────────
    known = set(seen)                                  # 本树声明的 FQN
    known_stems = {f.stem for f in files}              # 兜底：未写 package 的情况
    for rel, text in texts.items():
        for imp in IMPORT_RE.findall(text):
            if imp.endswith(".*") or imp.startswith(NON_LOCAL_PREFIXES):
                continue
            if imp in known or Path(imp).name in known_stems:
                continue
            problems.append(
                f"{_posix(rel)} 的 `import {imp};` 在本树内解析不到"
                " —— 要么加源文件，要么它是外部 jar（那时把 jar 加进 libs.txt 并配 -cp）"
            )
    return problems

def _tool_available(tool: str) -> bool:
    return shutil.which(tool) is not None

def check_compile(version_dir: Path, javac: str, out_root: Path) -> list[str]:
    """整套编译到**本版专属** out 目录。绝不只编入口。"""
    problems: list[str] = []
    src = version_dir / "src"
    files = source_files(src)
    if not files or not any(f.suffix == ".java" for f in files):
        return problems                                  # 非 Java 项目：无编译器约定

    if not _tool_available(javac):
        return [f"找不到 `{javac}`，跳过编译检查（装 JDK 后重跑即可）"]

    out_dir = out_root / version_dir.name
    out_dir.mkdir(parents=True, exist_ok=True)

    # `-implicit:none` 是关键：不带它时，若 -sourcepath 能爬到兄弟版本的目录，
    # javac 会**隐式编译兄弟版本的源文件**，表面编译成功、实际拉错实现。
    cmd = [
        javac, "-encoding", "UTF-8", "-implicit:none",
        "-sourcepath", str(src),
        "-d", str(out_dir),
        # 只从本版 src 找源码：显式列出，杜绝隐式搜索（绝不只编入口）
        *[str(src / f) for f in files if f.suffix == ".java"],
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        # javac 的错误行里带绝对路径，缩成相对版本区，输出短一点。
        # Windows 下 javac 给的是 `\`，先统一成正斜杠再替换，否则一条也不缩。
        detail = detail.replace("\\", "/")
        for pre in (str(version_dir.parent), str(version_dir)):
            detail = detail.replace(pre.replace("\\", "/") + "/", "")
        problems.append(f"编译失败（{len(files)} 个源文件整套编译）：\n{detail}")
        return problems

    # 入口存在性：编过了还要有一个可运行的入口，且入口名必须唯一
    classes = sorted(p.relative_to(out_dir).as_posix() for p in out_dir.rglob("*.class"))
    mains = [c for c in classes if c.endswith("Main.class") or "Main$" in c]
    if not mains and any(f.stem.lower().endswith("main") for f in files):
        problems.append("有 *Main 源文件，但编译产物里没有对应的 Main.class —— 检查包声明或类名")
    return problems

def check_classpath_hygiene(version_dir: Path, out_root: Path) -> list[str]:
    """本版 out 目录必须专属：兄弟版本的 out 不得被复用。"""
    problems: list[str] = []
    for name in BUILD_DIRS:
        inside = version_dir / name
        if inside.is_dir():
            problems.append(
                f"版本目录里有 {{name}}/（= {name}/）—— 构建产物不属于版本产物；"
                "把它放到仓库根，且**每版一个独立 out 目录**（out/<版本名>）"
            )
    # 本版 out 是否被兄弟版本共享：同名 out 目录里出现不属于本版的类。
    # 比的是**顶层类名**：javac 会给匿名类/内部类产出 `Outer$1.class`、
    # `Outer$State.class`，它们的 stem 带 `$` 后缀，直接跟源文件 stem 比会全部
    # 误判成「兄弟版本的类」—— 而真被污染的报告就淹在假阳性里了。
    own_stems = {f.stem.split("$", 1)[0] for f in source_files(version_dir / "src")}
    own = out_root / version_dir.name
    if own.is_dir():
        foreign = [p.name for p in own.rglob("*.class")
                   if p.stem.split("$", 1)[0] not in own_stems]
        if foreign:
            problems.append(
                f"{_posix(own)} 里出现了本版源码之外的类（{'、'.join(sorted(set(foreign))[:5])}）"
                " —— out 目录被兄弟版本污染了，删掉重建"
            )
    return problems

def audit_version(version_dir: Path, javac: str, out_root: Path) -> list[str]:
    problems = check_static(version_dir)
    problems.extend(check_classpath_hygiene(version_dir, out_root))
    problems.extend(check_compile(version_dir, javac, out_root))
    return problems

def _write_report(version_dir: Path, problems: list[str]) -> None:
    """在版本目录写下 `check_code.txt` —— 布局审计（audit_layout.py 4.7）读它判门。

    首行是 `√`（通过）或 `×`（未通过）。文件在 `.gitignore` 与 `IGNORE_GLOBS` 里，
    不作为交付产物。
    """
    mark = "√" if not problems else "×"
    lines = [f"{mark} check_code.py {version_dir.name}"]
    lines.extend(f"    - {p}" for p in problems)
    (version_dir / "check_code.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

def build_run_contract(area_name: str) -> str:
    """规范节里「编译与运行」一节的正文 —— 唯一真源，`audit_layout.py` 从这里取。"""
    out: list[str] = []
    out.append("**每个版本独立编译、独立 out、独立工作目录**（硬性）")
    out.append("")
    out.append(
        "版本区里多个 vNN 常常复用同名包（`model`/`service`/`controller`/`ui`）"
        "与同名默认包入口 `Main`。这在**布局上合法**（`src/` 内部不受约束），"
        "但一旦编进同一个 `out/` 或从同一个 classpath 运行，javac/java 会挑错"
        "`Main.class`、或从兄弟版本拉错 `model.Player` —— 表现就是「找不到主类」"
        "或静默跑错版本。所以编译与运行方式必须固定为下面这条："
    )
    out.append("")
    out.append("```bash")
    out.append("# 在 vNN/ 里执行；每版一个独立 out 目录，绝不共用")
    out.append("javac -encoding UTF-8 -implicit:none -d ../out/vNN $(find src -name '*.java')")
    out.append("java  -cp ../out/vNN Main")
    out.append("```")
    out.append("")
    out.append("三条硬约束：")
    out.append("")
    out.append(
        "1. **一个版本 = 一个 out 目录 = 一个工作目录。** 绝不复用 `out/`；"
        "目录名取版本名（`out/v03`），出问题时一眼能看出是谁的产物。"
    )
    out.append(
        "2. **绝不只编入口。** 永远 `$(find src -name '*.java')` 整套编译 —— "
        "只编 `Main.java` 时依赖不在 sourcepath，报 `cannot find symbol`，"
        "或运行期 `NoClassDefFoundError`。"
    )
    out.append(
        "3. **带 `-implicit:none`。** 不带它时 javac 会沿 sourcepath 隐式编译"
        "**兄弟版本的源文件**，表面成功、实际拉错实现。"
    )
    out.append("")
    out.append(
        "> **结构性避免（推荐，非强制）**：各版顶层包根取版本身份（`v01` 用 `planwar.*`、"
        "`v02` 用 `singleton.*`），永久消除同名包冲突；入口类名唯一（`ShapeMain`、`CarMain`，"
        "绝不允许有效 classpath 里有两个 `Main`）。"
    )
    out.append("")
    out.append("**机器检查**")
    out.append("")
    out.append(
        "本节规则由 `poly-version-generator/scripts/check_code.py` 执行 —— "
        "抽查重复类名、未解析 import、整套编译、out 污染四类真实故障："
    )
    out.append("")
    out.append("```bash")
    out.append(f"python poly-version-generator/scripts/check_code.py {area_name}")
    out.append("```")
    out.append("")
    out.append(
        "**检查不通过就不得进入下一步**（写报告、打包提交、横向对比都不许开始）。"
        "快速反应："
    )
    out.append("")
    out.append("- 运行时 `NoClassDefFoundError`/`ClassNotFoundException` → `-cp`/`cwd` 错 → "
               "确认 out 目录属于当前版本。")
    out.append("- 编译时 `cannot find symbol` → 只编了入口 → 补上 `$(find src -name '*.java')`。")
    out.append("- 无报错但行为错 → 选中了兄弟版本的 `model`/`Main` → 用唯一包根解决。")
    out.append("")
    return "\n".join(out)

def cmd_check(area_root: Path, only: str | None, javac: str,
              out_root: Path) -> int:
    versions = find_versions(area_root)
    if not versions:
        print(f"× {_posix(area_root)}/ 下没有 vNN 形式的版本目录")
        return 1
    if only:
        versions = [v for v in versions if v.name == only]
        if not versions:
            print(f"× 没有版本目录 {_posix(area_root)}/{only}")
            return 1

    out_root.mkdir(parents=True, exist_ok=True)
    print(f"检查 {_posix(area_root)}/ —— 共 {len(versions)} 个版本")
    print(f"编译输出：{_posix(out_root)}/<版本名>/   （每版独立，绝不共用）")
    print()

    failed = 0
    for v in versions:
        problems = audit_version(v, javac, out_root)
        _write_report(v, problems)
        if problems:
            failed += 1
            print(f"× {v.name}  FAIL")
            for p in problems:
                for i, line in enumerate(p.split("\n")):
                    print(f"    - {line}" if i == 0 else f"      {line}")
        else:
            print(f"√ {v.name}  PASS")

    print()
    if failed:
        print(f"结果：{len(versions) - failed}/{len(versions)} PASS，{failed} 处未通过")
        print("→ 不得进入下一步：先修到全部 PASS 再写报告 / 打包 / 横向对比。")
        print("  报告已写入各版本目录的 check_code.txt（审计 4.7 会读它）。")
        return 1
    print(f"结果：{len(versions)}/{len(versions)} 全部 PASS —— 可以进入下一步")
    return 0

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="check_code.py",
        description="检查各版本的编译与类路径卫生：每版独立 out、整套编译、无同名冲突。",
    )
    ap.add_argument("version_area", type=Path,
                    help="版本区目录，如 SingletonPattern/poly-singleton")
    ap.add_argument("--only", default=None, help="只检查某一个版本，如 --only v03")
    ap.add_argument("--javac", default="javac", help="编译器可执行名（默认 javac）")
    ap.add_argument("--out-root", type=Path, default=None,
                    help="编译输出根目录（默认 <版本区>/../out）")
    args = ap.parse_args(argv)

    _setup_stdout()

    area_root: Path = args.version_area
    if not area_root.is_dir():
        print(f"× 目录不存在：{_posix(area_root)}")
        return 1

    out_root = args.out_root or (area_root.parent / "out")
    return cmd_check(area_root, args.only, args.javac, out_root)

if __name__ == "__main__":
    sys.exit(main())
