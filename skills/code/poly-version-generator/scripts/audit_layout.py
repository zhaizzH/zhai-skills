#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""poly-version-generator 的目录规范：唯一真源 + 审计器 + 规范节生成器。

规范只管「版本产物放在哪、叫什么名字」，**不管代码怎么写**。
每个版本是既有项目的**完整源码快照**，只锁 `src/`，内部一律不管。

# 配置行（区根文档里，全部可选）

    - `<Xxx>` = `MergeSort`          占位符映射（本项目现无内置占位符，留作扩展）
    - `required` = `src/, 说明.md`    版本根必需项；写了就只查列出的这些
    - `entry` = `src`                入口模式（本 profile 一般不用）

不写任何配置行 = 只查 `src/`。

# 用法

    python audit_layout.py <版本区>                    # 审计
    python audit_layout.py <版本区> --only v03         # 只审一个
    python audit_layout.py <版本区> --emit-spec -o spec.md
    python audit_layout.py <版本区> --emit-spec --apply-spec -o <版本区>/项目总结.md

退出码：0 = 全部 PASS；1 = 有版本 FAIL（或用法/参数错误）。

依赖：仅标准库。Windows / macOS / Linux 均可。
"""

from __future__ import annotations

import argparse
import dataclasses
import fnmatch
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

def _setup_stdout() -> None:
    """非 UTF-8 控制台（Windows GBK）下 `√`/`×` 等标记不要抛异常中断审计。"""
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

# ══════════════════════════════════════════════════════════════════════
# 一、区根文档 —— 一个版本区**只有一份** md
# ══════════════════════════════════════════════════════════════════════
AREA_SUMMARY = "项目总结.md"

# 过渡期兼容：老区还在用 CONTRACT.md 装映射行与规范节。审计器**读得到**它，
# 但同时会把「区根还留着旧文档」报成待修正（见 LEGACY_AREA_DOCS）。
AREA_DOC_CANDIDATES = (AREA_SUMMARY, "CONTRACT.md")

# 迁移前遗留的区根文档：不该再存在，内容应已并入 AREA_SUMMARY
LEGACY_AREA_DOCS = ("CONTRACT.md", "PLAN.md", "REPORT.md")

# 迁移前遗留的版本内文档：版本目录里不放 md
LEGACY_VERSION_DOCS = ("MANIFEST.md",)

# 配置行总则：`键` = `值`。值可空，允许逗号续接（每值一对反引号）。
CONFIG_RE = re.compile(
    r"`([^`]+)`\s*[:=]\s*`([^`]*)`"
    r"((?:[ \t]*,[ \t]*`[^`]+`(?![ \t]*[:=]))*)"
)

# 配置行键：让 profile 的硬编码值可被区文档覆盖，换实验不必改脚本。全部可选。
#
#   entry       入口文件模式（glob 或字面名，可含占位符）
#   required    版本根必需项，逗号分隔。写了就只查列出的这些
CONFIG_KEYS: tuple[str, ...] = ("entry", "required")

# 「值是逗号分隔清单」的键：按出现次序合并，不能取末值。
CONFIG_LIST_KEYS: tuple[str, ...] = ("required",)

# 旧 profile 行/映射行的键名
PROFILE_KEY = "profile"

# 已失效的映射键：`.iml` 不再进版本区，老区文档里的 `<模块>` 映射指空。
DEAD_MAPPING_KEYS: tuple[str, ...] = ("模块",)

def _config_pairs(text: str) -> list[tuple[str, str]]:
    """从区文档里抽出所有 `键 = 值` 对子，保持出现次序（清单键要按次序合并）。"""
    pairs: list[tuple[str, str]] = []
    for line in text.split("\n"):
        m = CONFIG_RE.search(line)
        if m:
            pairs.append((m.group(1), m.group(2) + m.group(3)))
    return pairs

def _live_mapping(mapping: dict[str, str]) -> dict[str, str]:
    """滤掉已失效的映射键，只留仍然生效的。"""
    return {k: v for k, v in mapping.items() if k not in DEAD_MAPPING_KEYS}

# 审计时一律不看的东西。增删时同步看一眼仓库根 .gitignore。
IGNORE_DIRS: set[str] = {
    "__pycache__", ".venv", "venv", ".idea", ".vscode",
    "bin", "out", "target", "build",
    "截图",
    ".pytest_cache", ".mypy_cache",
}

IGNORE_GLOBS: list[str] = [
    "*.class", "*.jar", "*.war", "*.ear",
    "*.iml", "*.iws", "*.ipr",
    "*.py[cod]",
    "~$*", ".~*", "*~", "*.swp", "*.swo",
    "*.log", "*.tmp", "*.bak",
    "Desktop.ini", "Thumbs.db",
]

# ══════════════════════════════════════════════════════════════════════
# 二、profile 定义 —— 改这里，审计规则跟着变
# ══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Profile:
    """一套版本区规矩。

    `spec` 是版本目录内的条目表：每条 = (相对 vNN/ 的路径, 必需?, 说明)。
    含 "/" 且结尾是 "/" 的是目录；`glob_required` 里的路径按通配匹配；
    其余是文件。说明会原样写进规范节的表格里，用祈使句、说清为什么。
    """

    key: str
    title: str
    intro: str
    spec: tuple[tuple[str, bool, str], ...]
    # 入口文件名模式（可含占位符）。空 = 本 profile 不指定入口。
    entry: str = ""
    # 通配必需项：路径 → glob
    glob_required: tuple[tuple[str, str], ...] = ()
    # 版本根允许出现、但不写进 SPEC 的文件后缀
    allowed_root_suffixes: frozenset[str] = frozenset()
    # 「多出顶层文件」的提示语
    stray_hint: str = ""

# ── profile：源码快照型（唯一）────────────────────────────────────────
#
# 每版是既有项目的**完整源码快照**，只锁 `src/`。
#
# 为什么不把 `.iml` 列进必需项（曾经列过，2026-09-22 撤掉）：
#   1. 它是 IDE 元数据，不是版本产物；
#   2. 它可推导，锁它换不来「每版能独立编译运行」；
#   3. 逐版改名与五版同名都出现过，锁名字等于把实验语义写进布局规范。
SNAPSHOT = Profile(
    key="source-snapshot",
    title="source-snapshot",
    intro="同一既有项目 N 种风格**各改一遍**，每版是完整源码快照，故只锁 `src/`。",
    spec=(
        ("src/", True,
         "该分支的完整源码快照，**照抄原项目的包结构**；内部有几个包、几个 "
         "`.java` 一律不管（每版是完整快照，不是单文件实现）"),
    ),
    glob_required=(),
    allowed_root_suffixes=frozenset(),
    stray_hint="版本根只该有 src/（IDE 文件不入库）",
)

PROFILES: dict[str, Profile] = {p.key: p for p in (SNAPSHOT,)}
DEFAULT_PROFILE = SNAPSHOT.key

# 区根共享文件：n 个版本共有，版本目录里不得出现同名文件
AREA_FILES: tuple[tuple[str, str], ...] = (
    (AREA_SUMMARY, "区根**唯一一份**文档：规范节 + 版本→风格映射 + 各版状态 + 横向结论"),
)

# ══════════════════════════════════════════════════════════════════════
# 三、工具函数
# ══════════════════════════════════════════════════════════════════════

def _is_ignored(rel: Path) -> bool:
    """相对路径是否属于「审计不看」的产物。"""
    if any(part in IGNORE_DIRS for part in rel.parts):
        return True
    return any(fnmatch.fnmatch(rel.name, g) for g in IGNORE_GLOBS)

def _expand(tmpl: str, mapping: dict[str, str]) -> str:
    """把模板里的 `<Xxx>` 换成实际名；没有映射则原样返回。"""
    out = tmpl
    for key, val in mapping.items():
        out = out.replace(f"<{key}>", val)
    return out

def _placeholder_key(tmpl: str) -> str | None:
    """`<报告名>` → `报告名`；非占位符 → None。"""
    if not tmpl.startswith("<"):
        return None
    end = tmpl.find(">")
    if end < 0:
        return None
    return tmpl[1:end]

def _is_placeholder(tmpl: str, mapping: dict[str, str]) -> bool:
    """下标是不是「还没有映射、名字待定」的必需品。"""
    key = _placeholder_key(tmpl)
    return key is not None and key not in mapping

def _classify_config(raw: list[tuple[str, str]]
                     ) -> tuple[dict[str, str], str | None, dict[str, str]]:
    """把 `键 = 值` 原始对子分成三类：占位符映射 / profile 名 / 配置覆盖。

    带尖括号 `<Xxx>` → 占位符映射；恰好是 `profile` → profile 名；
    裸标识符且属 CONFIG_KEYS → 配置覆盖；其它 → 丢弃。

    清单键（`required`）按**出现次序合并**（值内去重靠下游），标量键取末值。
    """
    mapping: dict[str, str] = {}
    config: dict[str, str] = {}
    profile_key: str | None = None
    seen: dict[str, list[str]] = {}

    for key, val in raw:
        key, val = key.strip(), val.strip()
        if key.startswith("<") and key.endswith(">"):
            mapping[key[1:-1]] = val
        elif key == PROFILE_KEY:
            profile_key = val
        elif key in CONFIG_KEYS:
            seen.setdefault(key, []).append(val)

    for key, vals in seen.items():
        if key in CONFIG_LIST_KEYS:
            config[key] = ", ".join(v.replace("`", "").strip() for v in vals)
        else:
            config[key] = vals[-1]
    return mapping, profile_key, config

def _read_area_meta(area_root: Path
                    ) -> tuple[dict[str, str], str | None, dict[str, str], Path | None]:
    """读区根文档里的配置行。优先 `项目总结.md`；读不到退回 `CONTRACT.md`。"""
    for name in AREA_DOC_CANDIDATES:
        doc = area_root / name
        if not doc.is_file():
            continue
        text = doc.read_text(encoding="utf-8", errors="replace")
        mapping, profile_key, config = _classify_config(_config_pairs(text))
        return mapping, profile_key, config, doc
    return {}, None, {}, None

def _posix(p: str | Path) -> str:
    """显示用路径：Windows 上也要正斜杠。"""
    return Path(p).as_posix()

def _actual_files(version_dir: Path) -> list[Path]:
    """版本目录内参与审计的实际文件，已忽略产物。"""
    out: list[Path] = []
    for p in sorted(version_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(version_dir)
        if _is_ignored(rel):
            continue
        out.append(rel)
    return out

def _allowed_root_names(mapping: dict[str, str], profile: Profile) -> set[str]:
    """版本根允许出现的文件/目录名（SPEC 展开后）。"""
    allowed: set[str] = set()
    for tmpl, _, _ in profile.spec:
        if tmpl.endswith("/"):
            allowed.add(Path(_expand(tmpl, mapping)).name)
        elif "/" not in tmpl:
            allowed.add(Path(_expand(tmpl, mapping)).name)
    return allowed

def _allowed_root_dirs(mapping: dict[str, str], profile: Profile) -> set[str]:
    """版本根允许出现的目录名（必需目录 + 声明项的父目录）。"""
    allowed: set[str] = set()
    for tmpl, _, _ in profile.spec:
        if tmpl.endswith("/"):
            allowed.add(Path(_expand(tmpl, mapping)).name)
        elif "/" in tmpl:
            allowed.add(Path(tmpl).parts[0])
    return allowed

def _stray_root_dirs(version_dir: Path, mapping: dict[str, str],
                     profile: Profile) -> list[str]:
    """版本根下不该出现的目录。"""
    allowed = _allowed_root_dirs(mapping, profile)
    return [p.name for p in sorted(version_dir.iterdir())
            if p.is_dir() and p.name not in allowed and not _is_ignored(Path(p.name))]

def _top_level_strays(version_dir: Path, mapping: dict[str, str],
                      profile: Profile) -> list[str]:
    """版本根下既不在 SPEC、后缀也不在白名单里的文件 —— 即「多出来的」。"""
    allowed = _allowed_root_names(mapping, profile)
    globs = [g for _, g in profile.glob_required]
    strays: list[str] = []
    for p in sorted(version_dir.iterdir()):
        if not p.is_file() or _is_ignored(Path(p.name)):
            continue
        if p.name in allowed or p.suffix.lower() in profile.allowed_root_suffixes:
            continue
        if any(fnmatch.fnmatch(p.name, g) for g in globs):
            continue
        strays.append(p.name)
    return strays

# ══════════════════════════════════════════════════════════════════════
# 四、审计
# ══════════════════════════════════════════════════════════════════════

def _check_glob_required(version_dir: Path, tmpl: str, glob: str,
                         mapping: dict[str, str], why: str) -> list[str]:
    """通配必需项：版本根下按 glob 找，数量必须恰为 1；给了映射还要名字对得上。"""
    found = [p for p in sorted(version_dir.glob(glob))
             if not _is_ignored(Path(p.name))]
    if not found:
        return [f"缺必需文件 {tmpl}（版本根目录下一个 {glob} 都没有）—— {why}"]
    if len(found) > 1:
        return ["版本根目录有 %d 个 %s（%s），只应有一个"
                % (len(found), glob, "、".join(p.name for p in found))]
    key = _placeholder_key(tmpl)
    if key and key in mapping:
        want = Path(_expand(tmpl, mapping)).name
        if found[0].name != want:
            return [f"文件名不符：期望 {want}，实际 {found[0].name}"]
    return []

def audit_version(version_dir: Path, mapping: dict[str, str],
                  profile: Profile) -> list[str]:
    """审计一个版本目录，返回违规描述列表（空 = PASS）。"""
    problems: list[str] = []

    # ── 4.1 版本目录里不得有区根共享的文档 ────────────────────────
    for name, _ in AREA_FILES:
        if (version_dir / name).exists():
            problems.append(f"版本目录里不该有 {name}（它是区根共享的文档，只有一份）")

    # ── 4.2 必需文件 / 必需目录 ───────────────────────────────────
    glob_map = dict(profile.glob_required)
    for tmpl, required, why in profile.spec:
        if not required:
            continue
        if tmpl in glob_map:
            problems.extend(_check_glob_required(
                version_dir, tmpl, glob_map[tmpl], mapping, why))
            continue
        if tmpl.endswith("/"):
            if not (version_dir / Path(tmpl)).is_dir():
                problems.append(f"缺必需目录 {_posix(tmpl)}")
            continue
        if _is_placeholder(tmpl, mapping):
            continue
        expanded = _expand(tmpl, mapping)
        if not (version_dir / expanded).is_file():
            problems.append(f"缺必需文件 {_posix(expanded)}")

    # ── 4.3 版本根下不该有的目录 ─────────────────────────────────
    for d in _stray_root_dirs(version_dir, mapping, profile):
        relax = "、".join(sorted(_allowed_root_dirs(mapping, profile))) or "无"
        problems.append(f"版本根下多出目录 {d}/（不在本 profile 的规范内；弹性区只有 {relax}）")

    # ── 4.4 多出来的顶层文件 ─────────────────────────────────────
    for stray in _top_level_strays(version_dir, mapping, profile):
        if stray in LEGACY_VERSION_DOCS:
            problems.append(
                f"版本目录里不该有 {stray} —— 每版不再各带一份文档，"
                f"其内容并入区根 {AREA_SUMMARY} 的对应版本小节"
            )
            continue
        hint = f"；{profile.stray_hint}" if profile.stray_hint else ""
        problems.append(f"多出顶层文件 {stray}（不在本 profile 的规范内{hint}）")

    return problems

def audit_area_docs(area_root: Path) -> list[str]:
    """区根不该再有旧文档：内容应已并入唯一的 `项目总结.md`。"""
    problems: list[str] = []
    for name in LEGACY_AREA_DOCS:
        if (area_root / name).is_file():
            problems.append(
                f"区根还有 {name} —— 现在只留一份 {AREA_SUMMARY}，"
                f"把 {name} 的内容并进去后删除该文件"
            )
    return problems

def find_versions(area_root: Path) -> list[Path]:
    """找出版本区里所有 `v数字` 形式的目录，按名字排序。"""
    if not area_root.is_dir():
        return []
    return sorted(p for p in area_root.iterdir()
                  if p.is_dir() and re.fullmatch(r"v\d+", p.name))

def _apply_config(profile: Profile, config: dict[str, str],
                  notes: list[str], mapping: dict[str, str] | None = None) -> Profile:
    """把区文档里的配置覆盖应用到 profile 上。不写任何键 = 逐字段相等（零迁移）。

    `required` 用「声明即替换」：一旦写了，就只检查列出的那些文件。
    """
    if not config:
        return profile

    changes: dict[str, object] = {}

    if "entry" in config:
        changes["entry"] = config["entry"].strip()

    if "required" in config:
        items = _split_config_list(config["required"])
        changes["spec"] = tuple((it, True, "") for it in items)
        changes["glob_required"] = ()
        notes.append(f"⚠ 区文档声明了 `required`，本次只检查这 {len(items)} 项")

    return dataclasses.replace(profile, **changes)

def _split_config_list(raw: str) -> list[str]:
    """逗号分隔的清单；支持中英文逗号。空串 → 空清单。"""
    raw = raw.strip()
    if not raw:
        return []
    return [p.strip() for p in re.split(r"[,，]", raw) if p.strip()]

def _resolve_profile(area_root: Path, explicit: str | None
                     ) -> tuple[Profile, dict[str, str], list[str]]:
    """定下本次审计/生成用哪套 profile，返回 (profile, mapping, 提示行)。"""
    mapping, doc_key, config, doc = _read_area_meta(area_root)
    notes: list[str] = []

    if explicit:
        profile = PROFILES.get(explicit)
        if profile is None:
            raise SystemExit(
                f"× 未知 profile：{explicit}（可选：{'、'.join(sorted(PROFILES))}）")
        if doc_key and doc_key != explicit:
            notes.append(f"⚠ 区文档声明的是 {doc_key}，本次按命令行给的 {explicit} 审")
        return _apply_config(profile, config, notes, mapping), mapping, notes

    key = doc_key or DEFAULT_PROFILE
    profile = PROFILES.get(key)
    if profile is None:
        raise SystemExit(
            f"× 区文档里的 profile `{key}` 不认识（可选：{'、'.join(sorted(PROFILES))}）")

    if doc_key is None:
        notes.append(f"⚠ 区文档里没有 `profile` 行，按默认 {DEFAULT_PROFILE} 审")
    if doc is not None and doc.name != AREA_SUMMARY:
        notes.append(
            f"⚠ 映射行读自 {doc.name}（过渡期兼容）—— "
            f"区根现在只留一份 {AREA_SUMMARY}，请把内容并过去"
        )
    return _apply_config(profile, config, notes, mapping), mapping, notes

def cmd_audit(area_root: Path, only: str | None,
              explicit_profile: str | None) -> int:
    versions = find_versions(area_root)
    if not versions:
        print(f"× {_posix(area_root)}/ 下没有 vNN 形式的版本目录")
        return 1

    if only:
        versions = [v for v in versions if v.name == only]
        if not versions:
            print(f"× 没有版本目录 {_posix(area_root)}/{only}")
            return 1

    profile, mapping, notes = _resolve_profile(area_root, explicit_profile)
    live = _live_mapping(mapping)
    print(f"审计 {_posix(area_root)}/ —— 共 {len(versions)} 个版本")
    print(f"profile：{profile.title}（{profile.intro}）")
    if live:
        print("映射：" + "，".join(f"{k} → {v}" for k, v in live.items()))
    else:
        print("映射：本 profile 不需要映射行（版本根只锁 src/）")
    for dead in DEAD_MAPPING_KEYS:
        if dead in mapping:
            notes.append(
                f"⚠ 区文档里的 `<{dead}>` 映射行已失效（`.iml` 不再进版本区），删掉它")
    for n in notes:
        print(n)
    print()

    failed = 0
    for v in versions:
        problems = audit_version(v, mapping, profile)
        if problems:
            failed += 1
            print(f"× {v.name}  FAIL")
            for p in problems:
                print(f"    - {p}")
        else:
            print(f"√ {v.name}  PASS")

    total = len(versions)

    doc_problems = audit_area_docs(area_root)
    if doc_problems:
        failed += 1
        total += 1
        print()
        print("× 区根文档  FAIL")
        for p in doc_problems:
            print(f"    - {p}")

    print()
    if failed:
        print(f"结果：{total - failed}/{total} PASS，{failed} 处有待修正")
        return 1
    print(f"结果：{total}/{total} 全部 PASS")
    return 0

# ══════════════════════════════════════════════════════════════════════
# 五、生成区根文档里的规范节
# ══════════════════════════════════════════════════════════════════════

EMIT_HEADER = "<!-- 本节由 poly-version-generator/scripts/audit_layout.py --emit-spec 生成，勿手改 -->"
EMIT_FOOTER = "<!-- 本节结束 -->"

def _display_width(s: str) -> int:
    """终端显示宽度：CJK 与全角标点按 2 列算，其余按 1 列。"""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in s)

def _pad(s: str, width: int) -> str:
    """按显示宽度左对齐补空格，让 `←` 在同一列。"""
    return s + " " * max(1, width - _display_width(s))

def _tree_rows(profile: Profile, mapping: dict[str, str]) -> list[tuple[int, str]]:
    """把 AREA_FILES + SPEC 摊平成 (缩进级, 文本)；级 0 = 区根，级 1 = vNN/ 内，级 2 = 目录内。"""
    rows: list[tuple[int, str]] = []
    for name, why in AREA_FILES:
        note = "（本文件）" if name == AREA_SUMMARY else ""
        rows.append((0, f"{_pad(name, 24)}← 区根共享：{why}{note}"))

    rows.append((0, "vNN/"))
    for tmpl, required, why in profile.spec:
        mark = "必需" if required else "弹性"
        if tmpl.endswith("/"):
            rows.append((1, f"{_pad(_posix(tmpl), 24)}← {mark}：{why}"))
        elif "/" in tmpl:
            rows.append((2, Path(_expand(_posix(tmpl), mapping)).name))
        else:
            rows.append((1, f"{_pad(_expand(_posix(tmpl), mapping), 24)}← {mark}：{why}"))
    return rows

def _tree_lines(area_name: str, profile: Profile,
                mapping: dict[str, str]) -> list[str]:
    """渲染文件树。分支符号由「同级中是否最后一项」决定，缩进由级数决定。"""
    rows = _tree_rows(profile, mapping)
    lines = [f"{area_name}/"]
    for i, (lvl, text) in enumerate(rows):
        nxt = next((l for l in rows[i + 1:]), None)
        last_at_level = nxt is None or nxt[0] < lvl

        prefix = ""
        if lvl == 1:
            parent_last = all(r[0] != 0 for r in rows[i + 1:])
            prefix = "    " if parent_last else "│   "
        elif lvl == 2:
            parent_last = all(r[0] != 1 for r in rows[i + 1:])
            prefix = ("    " if parent_last else "│   ") + "    "

        if lvl == 0 and text == "vNN/":
            lines.append(f"└── {text}")
            continue
        lines.append(f"{prefix}{'└──' if last_at_level else '├──'} {text}")
    return lines

def _section_head(area_name: str, profile: Profile,
                  mapping: dict[str, str]) -> list[str]:
    """规范节的开头：标题、说明、profile 声明、树。"""
    out: list[str] = [EMIT_HEADER, "", "## 一、目录与文件树（硬性）", ""]
    out.append(
        f"`{area_name}/` 下每个版本一个独立目录，互不写入。"
        "**下面每一项都是规则**，不是建议：违反 = 文件审计 FAIL。"
    )
    out.append("")
    out.append(f"- `profile` = `{profile.title}`（{profile.intro}）")
    out.append("")
    out.append("```")
    out.extend(_tree_lines(area_name, profile, mapping))
    out.append("```")
    out.append("")
    return out

def _mapping_block(mapping: dict[str, str]) -> list[str]:
    out: list[str] = []
    live = _live_mapping(mapping)
    if live:
        out.append("**本实验的映射**（占位符 → 实际名）")
        out.append("")
        for k, v in live.items():
            out.append(f"- `<{k}>` = `{v}`")
        out.append("")
    return out

def _required_tables(profile: Profile, mapping: dict[str, str]) -> list[str]:
    out: list[str] = []
    out.append("**必需**（缺一即 FAIL）")
    out.append("")
    out.append("| 路径 | 说明 |")
    out.append("|------|------|")
    for tmpl, required, why in profile.spec:
        if required:
            out.append(f"| `{_expand(_posix(tmpl), mapping)}` | {why} |")
    out.append("")

    elastic = [(t, w) for t, r, w in profile.spec if not r]
    if elastic:
        out.append("**弹性区**（可自由增删，风格差异的落点）")
        out.append("")
        out.append("| 目录 | 说明 |")
        out.append("|------|------|")
        for tmpl, why in elastic:
            out.append(f"| `{_expand(_posix(tmpl), mapping)}` | {why} |")
        out.append("")
    return out

def _doc_layer_block() -> list[str]:
    """文档层：区根只有一份 md，版本内一份不留。"""
    out: list[str] = []
    out.append("**文档只有区根一份**（硬性）")
    out.append("")
    out.append(
        f"整个版本区只留 `{AREA_SUMMARY}` 这一份 md（区根），"
        "**版本目录里不放任何文档** —— 曾经的每版 `MANIFEST.md` 已取消，"
        "它记的「本版有什么、本版取舍、校验记录」并进区根总结的对应版本小节。"
    )
    out.append("")
    out.append(
        "> 少写文档 ≠ 少记信息。版本内没有文件清单时，最容易丢的是"
        "「这版为什么多/少一个文件」——那份解释现在归区根总结的版本小节。"
    )
    out.append("")
    return out

def build_snapshot_section(area_name: str, mapping: dict[str, str],
                           profile: Profile = SNAPSHOT) -> str:
    """source-snapshot profile 的规范节。"""
    out: list[str] = _section_head(area_name, profile, mapping)
    out.extend(_mapping_block(mapping))
    out.extend(_required_tables(profile, mapping))

    out.append("**唯一落点：版本根只有 `src/`**（硬性）")
    out.append("")
    out.append(
        f"版本根除 `src/` 外不放任何东西 —— 手写文档、探针、报告、构建产物"
        f"（`out/` 等）都不算数，审计不看你也不该提交。对照文档属于区根 "
        f"`{AREA_SUMMARY}`，编译与临时探针放仓库根的 `out/`。"
    )
    out.append("")
    out.append(
        "**不收 IDE 文件**（`.iml`/`.iws`/`.ipr`/`.idea/`）：它们是 IDE 本机状态、"
        "可重新生成，不是版本产物。需要编译或截图时让 IDE 自己认 source root 即可。"
    )
    out.append("")
    out.append(
        "**本规范不管代码怎么写**：抽象方式、模块拆分、命名细节、依赖选择都不受约束 —— "
        "只保证不同版本的同名文件能直接对照（`diff v01/src/x v02/src/x` 有锚点）。"
    )
    out.append("")

    out.append("**禁止**")
    out.append("")
    out.append(
        "1. 禁止改 `src/` 内的任何源码 —— 快照须与原分支逐字一致，"
        "要改写法就回源区改、重新导出；就地编辑会让 `diff` 混入手工痕迹，"
        "各版对照的可信度随之失效。"
    )
    out.append(
        "2. 禁止在版本根放 `src/` 之外的任何文件或目录。"
    )
    out.append(
        f"3. 禁止在版本目录里放任何 md —— 文档只有区根一份 `{AREA_SUMMARY}`。"
    )
    out.append("")

    out.extend(_doc_layer_block())

    out.append("> 本规范只管「放在哪、叫什么」，不管「怎么写」。")
    out.append("")
    return "\n".join(out)

def build_section(area_name: str, mapping: dict[str, str], profile: Profile) -> str:
    """按 profile 生成区根文档里那一节规范，含首尾边界标记。"""
    body = build_snapshot_section(area_name, mapping, profile)
    return f"{body}\n{EMIT_FOOTER}"

def _apply_spec(dest: Path, section: str) -> int:
    """用生成的规范节**原地替换** `项目总结.md` 里「一、目录与文件树」那一段。

    替换边界是生成物自带的 `EMIT_HEADER`→`EMIT_FOOTER`。**找不到标记就不写**。
    """
    text = dest.read_text(encoding="utf-8", errors="replace")
    start = text.find(EMIT_HEADER)
    end = text.find(EMIT_FOOTER)
    if start < 0 or end < 0 or end < start:
        print(f"× {_posix(dest)} 里找不到规范节的边界标记"
              f"（`{EMIT_HEADER}` … `{EMIT_FOOTER}`）—— 先跑 --emit-spec 生成一节，"
              "或手工把上一节替换进去，本脚本不猜边界")
        return 1
    end += len(EMIT_FOOTER)
    dest.write_text(text[:start] + section.strip() + text[end:], encoding="utf-8")
    print(f"√ 已就地替换 {_posix(dest)} 的规范节（其余各节原样保留）")
    return 0

def cmd_emit(area_root: Path, mapping: dict[str, str], profile: Profile,
             dest: Path | None) -> int:
    section = build_section(area_root.name, mapping, profile)
    if dest is None:
        sys.stdout.write(section + "\n")
        return 0

    parent = dest.parent
    if parent and not parent.is_dir():
        print(f"× 目标目录不存在：{_posix(parent)} —— 先建目录，或改 `-o` 指向已存在的路径")
        return 1
    dest.write_text(section + "\n", encoding="utf-8")
    print(f"√ 已写出 {_posix(dest)}（profile = {profile.title}）")
    print(f"  用它替换 {AREA_SUMMARY} 里的「一、目录与文件树」那一节；其余各节保留不动。")
    return 0

# ══════════════════════════════════════════════════════════════════════
# 六、命令行
# ══════════════════════════════════════════════════════════════════════

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="audit_layout.py",
        description="审计 n 个对照版本的目录是否符合 SPEC（本文件即规范真源）。",
    )
    ap.add_argument("version_area", type=Path,
                    help="版本区目录，如 SingletonPattern/poly-singleton")
    ap.add_argument("--emit-spec", action="store_true",
                    help="生成区根文档里的规范节 markdown，而不是审计")
    ap.add_argument("--apply-spec", action="store_true",
                    help="配合 --emit-spec：把生成的规范节**就地替换**进 -o 指向的区文档")
    ap.add_argument("-o", "--out", type=Path, default=None,
                    help="配合 --emit-spec：写到文件（不给则打到 stdout）")
    ap.add_argument("--profile", default=None,
                    help=f"指定 profile（{'、'.join(sorted(PROFILES))}）；不给则读区文档")
    ap.add_argument("--only", default=None,
                    help="只审计某一个版本，如 --only v03")
    args = ap.parse_args(argv)

    _setup_stdout()

    area_root: Path = args.version_area
    if not area_root.is_dir():
        print(f"× 目录不存在：{_posix(area_root)}")
        return 1

    if args.emit_spec:
        if args.apply_spec and args.out is None:
            print("× --apply-spec 需要 -o 指定要替换的区文档（如 -o 项目总结.md）")
            return 1
        if args.only:
            print("⚠ --only 对 --emit-spec 无意义，本次忽略")
        profile, mapping, notes = _resolve_profile(area_root, args.profile)
        for n in notes:
            print(n)
        if args.apply_spec:
            return _apply_spec(args.out, build_section(area_root.name, mapping, profile))
        return cmd_emit(area_root, mapping, profile, args.out)

    return cmd_audit(area_root, args.only, args.profile)

if __name__ == "__main__":
    sys.exit(main())
