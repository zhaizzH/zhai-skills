#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""poly-version-generator 的目录规范：唯一真源 + 审计器 + 规范节生成器。

本文件是「n 个对照版本产出到哪、叫什么名字」的**唯一真源**。
其它地方（SKILL.md 的说明、各区 `项目总结.md` 的规范节）都从这里派生，
不要再手抄一份树 —— 手抄的那份一定会漂。

# 一套 profile：poly-version

版本是**同一目标、整体结构相同**的若干实现，内部命名等细节各版自定。
版本根只锁 `src/`，`src/` 内部一律不管（分包、拆几个文件、命名都由各版自定）。

无行数上限、无单文件约束、无 `提交/` 提交包 —— 只保证一件事：
**不同版本的同名文件能直接对照**，`diff v01/x v02/x` 有锚点。

保留的检查只有交付用词（版本号/风格名/设计模式名/「契约」+ 文件头编译运行命令）——
各版要能当独立的人写的东西交出去，源码里不能留横向对照的内部概念。

一句话：规范只管「放在哪、叫什么」，不管「怎么写」。「怎么写」由各版自定。

# 四种用法（审计 / 单版审计 / 生成规范节 / 省略 profile 行）

    # 审计：逐个版本比对实际文件与 SPEC，输出 PASS/FAIL 表
    python audit_layout.py SingletonPattern/poly-singleton

    # 只审一个版本
    python audit_layout.py SingletonPattern/poly-singleton --only v03

    # 生成区根文档里那一节规范（第一次建版本区时做一次；树变了再生成一次）
    python audit_layout.py SingletonPattern/poly-singleton --emit-spec -o spec.md

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

def build_run_contract(area_name: str) -> str:
    """转发到 check_code.py —— 编译/运行约定的真源在那里。

    不在本文件里重写一份：两处规则必然漂，而「每版独立 out」的表述与
    check_code.py 实际执行的检查必须逐字一致。
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import check_code
    return check_code.build_run_contract(area_name)


def _setup_stdout() -> None:
    """让 stdout 在非 UTF-8 控制台（Windows GBK 是常态）下**不要抛异常**。

    审计输出里有 `⚠` / `√` / `×` 这类标记。GBK 编不出 `⚠`（U+26A0），
    旧版直接 `print` 会抛 UnicodeEncodeError **中断整个审计** —— 看起来像脚本坏了，
    实际只是标记打不出来。实测 5 个版本区里有 3 个因此没跑完。

    改成 `errors="replace"`：编不出的字符降级成 `?`，审计照常跑完并给出结论。
    设了 `PYTHONIOENCODING=utf-8` 时输出与改造前逐字一致。
    """
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        # 老 Python 或 stdout 被重定向成不支持 reconfigure 的对象 —— 退回原样，
        # 不做兜底包装：宁可保持今天的可见行为，也不要引入新的输出路径。
        pass

# ══════════════════════════════════════════════════════════════════════
# 一、区根文档 —— 一个版本区**只有一份** md
# ══════════════════════════════════════════════════════════════════════
#
# 曾经是四份：区根 PLAN.md / CONTRACT.md / REPORT.md，外加每版一份 MANIFEST.md。
# 用户 2026-09-22 定：**不要那么多 md**，区根只留一份总结，版本目录里一份不留。
#
# 于是四份的职责合并成一份，写在区根的这个文件里：
#
#   · 目录规范（本脚本 `--emit-spec` 生成的那一节）
#   · 版本 → 风格映射总表、生成批次、各版状态表   （原 PLAN.md）
#   · 各版实际产出了什么、本版取舍、校验记录      （原每版 MANIFEST.md，现按版本分小节）
#   · 横向对比结论                                （原 REPORT.md）
#
# 名字取 `项目总结.md`（用户指定）。要点：**版本目录里不再有任何 .md** ——
# `MANIFEST.md` 已取消，其内容并入区根总结的对应小节。
#
# ⚠️ 少写文档 ≠ 少记信息。信息总量不该缩水，只是从「四份分散」变成「一份分节」。
# 版本内不再有文件清单时，最容易丢的是「这版为什么多/少一个文件」——
# 那份解释现在归区根总结的版本小节。
AREA_SUMMARY = "项目总结.md"

# 过渡期兼容：老区还在用 CONTRACT.md 装映射行与规范节。审计器**读得到**它，
# 但同时会把「区根还留着旧文档」报成待修正（见 LEGACY_AREA_DOCS）——
# 读是为了不让你在迁移前连映射都丢，报是为了别让旧文档长期挂着。
AREA_DOC_CANDIDATES = (AREA_SUMMARY, "CONTRACT.md")

# 迁移前遗留的区根文档：不该再存在，内容应已并入 AREA_SUMMARY
LEGACY_AREA_DOCS = ("CONTRACT.md", "PLAN.md", "REPORT.md")

# 迁移前遗留的版本内文档：版本目录里不放 md
LEGACY_VERSION_DOCS = ("MANIFEST.md",)

# 占位符写法：`<Xxx>`；映射行格式见 _read_area_meta
PLACEHOLDER_RE = re.compile(r"^<[^<>]*>$")
# 配置行总则：`键` = `值`。一条正则收下三类键，形状区分：
#
#     `profile`   = `poly-version`        → profile 选择
#     `<Xxx>`     = `SingletonDemo`        → 占位符映射（带尖括号）
#     其它标识符   = 值                     → 配置覆盖（见 CONFIG_KEYS）
#
# 这是对旧 MAPPING_RE / PROFILE_RE 的收口：两者的既有行为都被包含，
# 所以**旧区文档的解析结果逐字不变**。
#
# 三点比「一对反引号夹一个值」更宽，都是被清单键逼出来的（见 CONFIG_LIST_KEYS）：
#
#   1. 值可空 —— 配置键都可留空（如 `required` = `` 表示「本版无必需产物」），而
#      `` `required` = `` ``（两个反引号之间什么都没有）在原来的 `[^`]+` 下
#      **根本匹配不到**，于是那一行被整个丢弃、键保持缺省 —— 「声明为空」静默失效。
#      改成 `[^`]*` 后空值能解析出来，再由 `_split_config_list` 归成空清单。
#   2. 值里放行逗号 —— 一个反引号对里可以写多项
#      （`` - `required` = `main.py, _pack.py` ``）。`[^`]+` 本来就不排除逗号，
#      这里仍是 `[^`]*`，无需改动。
#   3. **逗号续接**：清单键的自然写法是每个值各自加一对反引号 ——
#      `` - `required` = `main.py`, `_pack.py` ``。原来的正则只收下 `main.py`，
#      第二个值连匹配都匹配不上，于是被静默丢弃（`_pack.py` 因而被判「多出顶层文件」）。
#      所以末尾那次重复允许「, `值`」链条。负向前瞻 `(?![ \t]*[:=])` 是关键：
#      它让续接**在下一个 `=` 处停下**，于是 `` `profile` = `a`, `required` = `b` ``
#      这种一行两个配置行还能被拆成两对，而不是把 `required` 当成一个文件名收走。
#
# 代价：正文里偶然出现的 `` `x` = `` `` 会被当成一个空值配置行。但「裸标识符且恰好
# 属于 CONFIG_KEYS」这层过滤还在（见 _classify_config），实际能命中的只有那五个键。
# 第 3 组是续接部分，**必须捕获**：它属于值，不是可选装饰。少了它，上面的
# `` `required` = `a`, `b` `` 虽然整行都被匹配，但捕获到的值只剩 `a` —— 换汤不换药。
CONFIG_RE = re.compile(
    r"`([^`]+)`\s*[:=]\s*`([^`]*)`"
    r"((?:[ \t]*,[ \t]*`[^`]+`(?![ \t]*[:=]))*)"
)
# 兼容别名：保留旧名，避免外部脚本 import 时断掉
MAPPING_RE = CONFIG_RE
PROFILE_RE = CONFIG_RE

# 配置行的键：让 profile 的硬编码值可被区文档覆盖，从而**换语言/换实验不必改脚本**。
# 全部可选；不写 = 用 profile 的缺省（即改造前的行为）。
#
#   entry       入口文件模式（glob 或字面名，可含占位符）。覆盖 profile 的入口约定。
#   required    版本根必需项，逗号分隔（可含占位符）。只列这些，不在列的**不检查**。
#
# 清单键接受**每个值各加一对反引号**的写法（多行或同一行都行）：
#
#     - `required` = `main.py`, `facts.py`
#
# `CONFIG_RE` 一次只收一对反引号，故 `_classify_config` 按出现次序合并同名清单键 ——
# 先转 dict 会静默丢掉第二项。只有清单键合并，其余键仍取末值。
#   java_checks `on`/`off`：交付用词与「头部编译运行命令」检查。
#   code_checks `on`/`off`：编译与类路径卫生检查（由 scripts/check_code.py 执行）。
#                           `off` 时审计不再要求 check_code.py 全 PASS。
CONFIG_KEYS: tuple[str, ...] = (
    "entry", "required", "java_checks", "code_checks",
)

# 其中「值是逗号分隔清单」的键。它们的自然写法是**每个值各自加一对反引号**：
#
#     - `required` = `main.py`, `facts.py`
#
# 而 `CONFIG_RE` 只认「一对反引号夹键 = 一对反引号夹值」，于是这条行只会读出
# `('required', 'main.py')` —— `facts.py` 静默丢失。所以这几个键要按**出现次序合并**，
# 不能像标量键那样取末值（见 `_classify_config`）。
CONFIG_LIST_KEYS: tuple[str, ...] = ("required",)

# 旧 profile 行/映射行的键名（`profile` 不带尖括号，其余带）
PROFILE_KEY = "profile"

# 已失效的映射键：老区文档里还留着 `<模块>` = `PlanWar`（那时 `.iml` 是版本根必需项）。
# 现在 `.iml` 不进版本区了，这行映射指的东西已不存在 —— 显示时滤掉，
# 免得审计输出与生成的规范节里保留一个指向空处的映射；
# 但要**报一句**提醒删（见 build_snapshot_section），静默忽略会让人以为它还生效。
DEAD_MAPPING_KEYS: tuple[str, ...] = ("模块",)


def _config_pairs(text: str) -> list[tuple[str, str]]:
    """从区文档里抽出所有 `键 = 值` 对子，**保持出现次序**。

    清单键要按次序合并、标量键要取末值，两者都依赖「谁先谁后」，所以返回列表而不是
    `dict`（`CONFIG_RE.findall` 也是列表，但它只能看到一个键一次 —— findall 不给
    匹配位置，没法知道同一键在文里出现过几处，也就无从按次序分组）。

    **逐行扫**：一行里只用该行的第一个匹配，这样`` `profile` = `a`, `required` = `b` ``
    这种一行两个配置行不会被续接规则粘成一个值（正则里的负向前瞻是第二道保险）。
    """
    pairs: list[tuple[str, str]] = []
    for line in text.split("\n"):
        m = CONFIG_RE.search(line)
        if m:
            # 第 3 组是逗号续接（`` `a`, `b` ``），属于值的一部分，拼回去
            pairs.append((m.group(1), m.group(2) + m.group(3)))
    return pairs


def _live_mapping(mapping: dict[str, str]) -> dict[str, str]:
    """滤掉已失效的映射键，只留仍然生效的（`<Xxx>`、`<报告名>` 等）。"""
    return {k: v for k, v in mapping.items() if k not in DEAD_MAPPING_KEYS}

# 审计时一律不看的东西
#
# 仓库根的 .gitignore 已覆盖大部分，但 .class 与 *.iml 必须在这里单独忽略：
# javac 跑一次就在 vNN/ 留下 .class，否则每个编译过的版本都会被误判 FAIL；
# 而 `.iml` 是 IntelliJ 的模块元数据 —— 用户 2026-09-22 定：**版本区不收录 IDE 文件**，
# 既不是版本产物，也不该出现在交付物里（仓库根的 `.idea/` 属于 IDE 自己维护的
# 目录，同样不是本技能管的东西）。
# 增删此清单时，顺带看一眼仓库根 .gitignore 的对应类别 —— 两处应当一致。
IGNORE_DIRS: set[str] = {
    "__pycache__", ".venv", "venv", ".idea", ".vscode",
    "bin", "out", "target", "build",
    "截图",                     # Screenshot.java 的产出目录
    ".pytest_cache", ".mypy_cache",
}

IGNORE_GLOBS: list[str] = [
    "*.class", "*.jar", "*.war", "*.ear",   # Java 编译产物
    "*.iml", "*.iws", "*.ipr",              # IntelliJ 模块 / 工作区元数据
    "*.py[cod]",                            # Python 字节码
    "~$*", ".~*", "*~", "*.swp", "*.swo",   # Office 锁文件 / 编辑器临时文件
    "*.log", "*.tmp", "*.bak",              # 日志与临时文件（与 .gitignore 同步）
    "check_code.txt",                      # check_code.py 的检查报告（审计 4.7 读它）
    "Desktop.ini", "Thumbs.db",
]


# ══════════════════════════════════════════════════════════════════════
# 二、profile 定义 —— 改这里，对应那一类版本区全跟着变
# ══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Profile:
    """一套版本区规矩。

    `spec` 是版本目录内的条目表，形状与旧版一致：每条 = (相对 vNN/ 的路径, 必需?, 说明)。
    含 "/" 且结尾是 "/" 的是目录；`glob_required` 里的路径按通配匹配；
    其余是文件。说明会原样写进规范节的表格里，用祈使句、说清为什么。
    """

    key: str
    title: str
    intro: str
    spec: tuple[tuple[str, bool, str], ...]
    # 入口文件模式（可含占位符，如 `<Xxx>Experiment.java`）。空 = 不校验具体名字，
    # 由区文档的 `entry` 配置行指派。
    entry: str = ""
    # 通配必需项：路径 → glob。用于名字由映射行指派的必需品。
    glob_required: tuple[tuple[str, str], ...] = ()
    # 交付源码禁用词与「文件头禁抄编译/运行命令」
    java_forbidden_words: tuple[str, ...] = ()
    java_forbidden_re: re.Pattern[str] | None = None
    java_header_command_check: bool = False
    # 是否要求 scripts/check_code.py 全 PASS（编译与类路径卫生）
    code_checks: bool = True
    # 版本根允许出现、但不写进 SPEC 的文件后缀
    allowed_root_suffixes: frozenset[str] = frozenset()
    # 「多出顶层文件」的提示语
    stray_hint: str = ""


# ── 交付源码里不得出现的词（硬性，用户 2026-09-22 要求）────────────────
#
# 「五版是一个学生的五份替补方案，每份都要能当独立的人写的代码交出去」这一前提，
# 意味着交付源码里**不能留横向对照的内部概念**。下面这些词一旦出现，读代码的人
# 立刻能看出这是同一批人的多版本实验 —— 而这正是「雷同双方记 0 分」要防的事。
#
# 分三类，都不是「风格差异」，而是**作者视角的泄漏**：
#
#   1. 版本代号与风格名：`v04`、`v04「结构化版」`、`（极简版）`。
#      版本号只在区根文档里存在，交付物里不该有。
#   2. 设计模式名：`策略模式`、`模板方法`、`显式参数化`。
#      写代码的人不会在文件头先给自己贴流派标签；写了就像在交「对照实验的第 N 组」。
#      结构本身可以留着，只是别自我命名。
#   3. 内部规则名与文档引用：`契约`、`契约 4.1`。
#      「契约」是本项目文档的简称，源程序里出现它，等于把开发文档引进了交付物；
#      读者看不到那份文档，只会觉得作者在跟某个他没见过的规范对齐。
#      要说「不得共用归并」就直接说事，别点名规则出处。
#
# 另外禁「头部编译运行命令」（见 JAVA_HEADER_COMMAND_RE）：`编译 javac …` /
# `运行 java -Dstdout.encoding=…` 这类行夹在文件头注释里像 README 摘抄。编译运行方法
# 属于 README.txt 的职责。**行内**提到 `javac` 不算（例如警告某个写法会多一次编译），
# 只查文件头部的独立命令行。
#
# ⚠️ 本类检查**只在这是单一 profile 时才会有实际效果**。若区文档用 `java_checks`
# 把它关掉（或词表为空），审计就不跑它 —— 见 `_apply_config`。
#
# ⚠️ 例外：「实验一 合并排序」**不算**禁用词 —— 它就是实验题目，报告标题与 README 都要用。
JAVA_FORBIDDEN_WORDS: tuple[str, ...] = (
    "契约",          # 本项目 CONTRACT.md 的内部简称（`契约 4.1` 也被这一条覆盖）
    "极简版", "务实版", "结构化版",      # 风格名（括号里的那种）
    "策略模式", "模板方法", "显式参数化",  # 设计模式名
)
# 版本代号单独用正则：`v04` 要匹配，而 `Vec`、`move`、`x86v04` 这类不该误伤。
JAVA_FORBIDDEN_RE = re.compile(r"\bv\d{2}\b")
# 文件头部（前 JAVA_HEADER_LINES 行）里的独立「编译/运行」命令行。
JAVA_HEADER_COMMAND_RE = re.compile(
    r"^\s*(?:\*\s*|/\*\s*|//\s*)?(?:编译|运行)\s*[:：]?\s*(?:javac|java)\b")
JAVA_HEADER_LINES = 15

# ── profile：整体结构相同、内部细节各异 ─────────────────────────────────
#
# 版本是**同一目标、整体结构相同**的若干实现：版本根的骨架逐字一致
# （同一份 `src/` 布局、同一批入口路径），各版**内部命名与实现细节**自定。
#
# 所以只锁 `src/`：里面原有几个包、几个源文件、怎么分包，一律不管。
# 无行数上限、无单文件约束、无 `提交/` 提交包 —— 规范只管「放在哪、叫什么」。
#
# 唯一保留的内容检查是交付用词（与文件头编译运行命令）：各版要能当**独立的人**
# 写的东西交出去，源码里不能留横向对照的内部概念（版本号、风格名、模式名、「契约」）。
#
# 为何仍不收 IDE 文件（`.iml`/`.idea/`）：它们是 IDE 本机状态，不是版本产物，
# 可重新生成，也不是交给老师的东西 —— 审计直接忽略。
POLY_VERSION = Profile(
    key="poly-version",
    title="poly-version",
    intro="同一目标整体结构相同、内部细节各异的若干实现，故只锁 `src/`。",
    spec=(
        ("src/", True,
         "该版本的完整源码，**整体结构与其它版一致**（同一批入口与包路径），"
         "内部命名与实现细节自定。本 profile 只锁 `src/`，内部有几个包、"
         "几个源文件一律不管；IDE 元数据（`.iml`/`.idea/`）不收录"),
    ),
    glob_required=(),
    java_forbidden_words=JAVA_FORBIDDEN_WORDS,
    java_forbidden_re=JAVA_FORBIDDEN_RE,
    java_header_command_check=True,
    allowed_root_suffixes=frozenset(),
    stray_hint="版本根只该有 src/（IDE 文件不入库，探针与构建产物放仓库根）",
)

PROFILES: dict[str, Profile] = {p.key: p for p in (POLY_VERSION,)}
DEFAULT_PROFILE = POLY_VERSION.key

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
    """把模板里的 `<Xxx>` / `<报告名>` / `<模块>` 换成实际名；没有映射则原样返回。"""
    out = tmpl
    for key, val in mapping.items():
        out = out.replace(f"<{key}>", val)
    return out


def _placeholder_key(tmpl: str) -> str | None:
    """`<报告名>` → `报告名`；非占位符 → None。

    占位符一律以 `<` 开头、以 `>` 结尾（见 `_expand`），故这里取首尾之间的一段。
    """
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
    """把 `键 = 值` 的原始对子分成三类：占位符映射 / profile 名 / 配置覆盖。

    形状即语义（见 `CONFIG_RE` 处的说明）：

        带尖括号 `<Xxx>`  → 占位符映射（旧 MAPPING_RE 的行为）
        恰好是 `profile`   → profile 名（旧 PROFILE_RE 的行为）
        裸标识符且属 CONFIG_KEYS → 配置覆盖（新增）
        其它               → 丢弃（例如正文里出现的 `` `foo` = `bar` `` 普通文字）

    **入参是 `findall` 的原始对子列表，不是 dict**。这一点是必需的：清单键的两种
    写法都要求「同一键可以出现多次」—— 每值一对反引号时，`CONFIG_RE` 会把
    `` `required` = `main.py`, `facts.py` `` 读成两个同键对子；就算值写在一个反引号对里
    （`main.py, facts.py`），分成两行写也还是同键两处。先转成 `dict` 会按同名键覆盖，
    静默丢掉后面那些值。这里按**出现次序**分组，再由下面的规则决定合并还是取末值。

    | 键 | 同名重复时 |
    |---|---|
    | `CONFIG_LIST_KEYS`（`required`） | **按次序合并**（值内去重） |
    | `profile`、`<Xxx>` 映射、其余标量键 | **取末值** —— 与改造前 `dict()` 的覆盖语义逐字一致 |
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
        # else: 不属于本机制的散文字（正文里偶然出现的 `x` = `y`），忽略

    for key, vals in seen.items():
        if key in CONFIG_LIST_KEYS:
            # 反引号是配置行的分隔记号，不可能是路径的一部分：续接写法会在捕获值里
            # 留下边界反引号（`main.py, `_pack.py``），去掉后拼成标准的逗号清单，
            # 交给 _split_config_list 统一切分。
            config[key] = ", ".join(v.replace("`", "").strip() for v in vals)
        else:
            config[key] = vals[-1]     # 末值：与改造前 dict() 的覆盖语义逐字一致
    return mapping, profile_key, config


def _read_area_meta(area_root: Path
                    ) -> tuple[dict[str, str], str | None, dict[str, str], Path | None]:
    """读区根文档里的配置行 —— 占位符映射、profile 声明、以及可选的配置覆盖。

    形如：

        - `profile` = `poly-version`
        - `<Xxx>` = `SingletonDemo`
        - `entry` = `<Xxx>Experiment.java`   ← 可选，覆盖 profile 的入口约定
        - `java_checks` = `off`             ← 可选，关掉交付用词检查

    返回 (mapping, profile_key, config, 实际读到的文档路径)。
    优先读 `项目总结.md`；过渡期读不到就退回 `CONTRACT.md`（并在审计输出里点明）。
    """
    for name in AREA_DOC_CANDIDATES:
        doc = area_root / name
        if not doc.is_file():
            continue
        text = doc.read_text(encoding="utf-8", errors="replace")
        # 传**对子列表**而不是 dict：清单键可能落在多对反引号里（见 _classify_config）
        mapping, profile_key, config = _classify_config(_config_pairs(text))
        return mapping, profile_key, config, doc
    return {}, None, {}, None


def _posix(p: str | Path) -> str:
    """显示用路径：Windows 上也要正斜杠。"""
    return Path(p).as_posix()


def _source_files(version_dir: Path, profile: Profile) -> list[Path]:
    """交付源码文件集（相对 vNN/ 的路径）—— 用词检查的对象。

    本 profile 只管「放在哪」：源码都在 `src/` 下，语言不限，
    所以**不按扩展名筛 Java**，而是把 `src/` 下所有参与审计的文件都当源码。
    `src/` 不在的版本由 4.2 报必需目录缺失，这里返回空。
    """
    src = version_dir / "src"
    if not src.is_dir():
        return []
    return [p for p in _actual_files(version_dir) if p.parts[0] == "src"]


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


def _entry_name(mapping: dict[str, str], profile: Profile) -> str | None:
    """本 profile 的入口文件名（展开占位符后）。

    `profile.entry` 优先；区文档的 `entry` 配置行可覆盖。没写则返回 None
    （本 profile 默认不锁具体入口名，入口路径由「各版整体结构一致」保证）。
    """
    tmpl = profile.entry
    if not tmpl:
        return None
    return Path(_expand(tmpl, mapping)).name


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
    """版本根允许出现的目录名（弹性区 + 必需目录）。`src/` 恒为允许的。"""
    allowed: set[str] = {"src"}
    for tmpl, _, _ in profile.spec:
        if tmpl.endswith("/"):
            allowed.add(Path(_expand(tmpl, mapping)).name)
        elif "/" in tmpl:
            allowed.add(Path(tmpl).parts[0])
    return allowed


def _stray_root_dirs(version_dir: Path, mapping: dict[str, str],
                     profile: Profile) -> list[str]:
    """版本根下不该出现的目录（源码目录、顺手建的空目录等）。"""
    allowed = _allowed_root_dirs(mapping, profile)
    return [p.name for p in sorted(version_dir.iterdir())
            if p.is_dir() and p.name not in allowed and not _is_ignored(Path(p.name))]


def _top_level_strays(version_dir: Path, mapping: dict[str, str],
                      profile: Profile) -> list[str]:
    """版本根下既不在 SPEC、后缀也不在白名单里的文件 —— 即「多出来的」。"""
    allowed = _allowed_root_names(mapping, profile)
    # 通配必需项（如 `*.docx`）也要放行：它们的名字由映射行指派，
    # 写在 SPEC 里的那个模板可能还没被映射展开成实际名 ——
    # 只认 SPEC 就会把实际的报告文件报成「多出顶层文件」。
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

def audit_version(version_dir: Path, mapping: dict[str, str],
                  profile: Profile) -> list[str]:
    """审计一个版本目录，返回违规描述列表（空 = PASS）。"""
    problems: list[str] = []

    # ── 4.1 版本目录里不得有区根共享的文档 ────────────────────────
    # 文档只有区根那一份。已取消的每版 MANIFEST.md 由 4.6 统一报（它同时是
    # 「多出的顶层文件」），这里不重复报 —— 同一条问题报两遍只会让人以为有两处要改。
    for name, _ in AREA_FILES:
        if (version_dir / name).exists():
            problems.append(f"版本目录里不该有 {name}（它是区根共享的文档，只有一份）")

    # ── 4.2 必需文件 / 必需目录 ─────────────────────────────────
    # 本 profile 只锁 `src/`。区文档的 `required` 声明的是 **`src/` 下的相对路径**
    # （如 `Main.java`、`pkg/Util.java`），所以非目录项统一挂到 `src/` 下查。
    # `src/` 本身恒为必需目录，不因 `required` 覆盖而消失。
    if not (version_dir / "src").is_dir():
        problems.append("缺必需目录 src/")
    for tmpl, required, why in profile.spec:
        if not required:
            continue

        if tmpl.endswith("/"):
            if not (version_dir / Path(tmpl)).is_dir():
                problems.append(f"缺必需目录 {_posix(tmpl)}")
            continue

        if _is_placeholder(tmpl, mapping):
            continue                      # 无映射：只查目录，不查具体名
        rel = Path("src") / _expand(tmpl, mapping)
        if not (version_dir / rel).is_file():
            problems.append(f"缺必需文件 {_posix(rel)}")

    # ── 4.4 交付源码里不得有横向对照的内部概念 ──────────────────
    # 本 profile 是唯一一套规矩：源码范围 = `src/` 下全部文件（语言不限）。
    # 单文件约束与行数上限已取消 —— 各版内部结构自定，规范不管「怎么写」。
    if profile.java_forbidden_words or profile.java_forbidden_re \
            or profile.java_header_command_check:
        for p in sorted(_source_files(version_dir, profile)):
            text = (version_dir / p).read_text(encoding="utf-8", errors="replace")
            hits: list[str] = [w for w in profile.java_forbidden_words if w in text]
            if profile.java_forbidden_re is not None:
                hits.extend(sorted({m.group(0)
                                    for m in profile.java_forbidden_re.finditer(text)}))
            if profile.java_header_command_check:
                for lineno, line in enumerate(text.split("\n")[:JAVA_HEADER_LINES], 1):
                    if JAVA_HEADER_COMMAND_RE.match(line):
                        hits.append("头部第 %d 行的「编译/运行」命令行" % lineno)
            if hits:
                problems.append(
                    f"{_posix(p)} 里出现了 {'、'.join(hits)} —— "
                    "交付源码不得带版本号、风格名、设计模式名或本项目文档的规则简称，"
                    "也不要在文件头抄编译运行命令（那属于 README.txt）；"
                    "每份要当一个独立的人写的代码交出去，别自我命名或引用开发文档"
                )

    # ── 4.5 版本根下不该有的目录 ─────────────────────────────────
    for d in _stray_root_dirs(version_dir, mapping, profile):
        problems.append(
            f"版本根下多出目录 {d}/（不在本 profile 的规范内；"
            f"弹性区只有 {'、'.join(sorted(_allowed_root_dirs(mapping, profile))) or '无'}）"
        )

    # ── 4.6 多出来的顶层文件 ─────────────────────────────────────
    # 已取消的 MANIFEST.md 也走这条（它确实是多出来的顶层文件），但给一句
    # 说明去向的话 —— 否则读者只被告知「不该在这儿」，不知道内容该搬去哪。
    for stray in _top_level_strays(version_dir, mapping, profile):
        if stray in LEGACY_VERSION_DOCS:
            problems.append(
                f"版本目录里不该有 {stray} —— 每版不再各带一份文档，"
                f"其内容并入区根 {AREA_SUMMARY} 的对应版本小节"
            )
            continue
        hint = f"；{profile.stray_hint}" if profile.stray_hint else ""
        problems.append(f"多出顶层文件 {stray}（不在本 profile 的规范内{hint}）")

    # ── 4.7 代码检查门 ──────────────────────────────────────────
    # 编译不通过、同类名冲突、out 被兄弟版本污染 —— 这些**不是布局问题**
    # （`src/` 内部本就不管），所以布局审计不能直接判。判据落在产物上：
    # `check_code.py` 跑过之后写下的 `check_code.txt`。文件在且首行 `√` = 通过。
    #
    # 为何不在这里现场调 javac：审计要能在无 JDK 的机器上跑（布局检查不该依赖工具链）。
    # 所以是「先跑 check_code.py，再跑审计」，审计只验它的结论。
    if profile.code_checks:
        report = version_dir / "check_code.txt"
        if not (version_dir / "src").is_dir():
            pass                          # 4.2 已报缺 src/，不再重复
        elif not report.is_file():
            problems.append(
                "缺 check_code.txt —— 先跑 `python poly-version-generator/scripts/"
                "check_code.py <版本区>`，全部 PASS 后再审计（编译不通过不得进入下一步）"
            )
        else:
            first = report.read_text(encoding="utf-8", errors="replace").split("\n")[0].strip()
            if not first.startswith("√"):
                problems.append(
                    f"check_code.txt 显示代码检查未通过（首行：{first or '空'}）—— "
                    "修到 check_code.py 全 PASS 再重跑"
                )

    return problems


def audit_area_docs(area_root: Path) -> list[str]:
    """区根不该再有旧文档：内容应已并入唯一的 `项目总结.md`。

    这条是**迁移提示**而不是布局洁癖：四份 md 并存时，改一处漏一处必然发生
    （本项目已经在报告技能上吃过一次亏）。留着旧文档，读者不知道哪份是真的。
    """
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
    """把区文档里的配置覆盖应用到 profile 上，返回展开后的 profile。

    不写任何配置键时返回的 profile 与原对象**逐字段相等** —— 这是既有版本区
    零迁移的依据。只认 `CONFIG_KEYS` 里的键，未知键已被
    `_classify_config` 丢弃。

    `required` 用「声明即替换」语义：一旦在区文档里写了，就**只检查**
    列出的那些文件，不在列的不再报「缺必需文件」。这是「核心 + 可配」的落点 ——
    产物清单则交给各区自定。

    `mapping` 可选，只用于自洽性检查（见末尾）—— 不给就跳过那一条。
    """
    if not config:
        return profile

    changes: dict[str, object] = {}

    if "java_checks" in config:
        raw = config["java_checks"].strip().lower()
        if raw not in ("on", "off"):
            raise SystemExit(f"× `java_checks` 只能是 `on` 或 `off`，得到 `{raw}`")
        if raw == "off":
            changes["java_forbidden_words"] = ()
            changes["java_forbidden_re"] = None
            changes["java_header_command_check"] = False

    if "code_checks" in config:
        raw = config["code_checks"].strip().lower()
        if raw not in ("on", "off"):
            raise SystemExit(f"× `code_checks` 只能是 `on` 或 `off`，得到 `{raw}`")
        changes["code_checks"] = (raw == "on")

    if "entry" in config:
        changes["entry"] = config["entry"].strip()

    if "required" in config:
        items = _split_config_list(config["required"])
        # 空清单是合法的：「本版没有任何必需产物」。
        # spec 的第三列是给人看的说明，配置行不给说明，故留空串。
        changes["spec"] = tuple((it, True, "") for it in items)
        changes["glob_required"] = ()
        notes.append(f"⚠ 区文档声明了 `required`，本次只检查这 {len(items)} 项")

    result = dataclasses.replace(profile, **changes)

    # ── 配置自洽性：`required` 替换了 spec，却没把入口文件列进去 ──────
    # `required` 是「声明即替换」：一旦写了，4.2 只查列出的项，入口不再计入必需。
    # 若 `required` 没含入口名，入口就不受 4.2 保护 —— 这里点明，不自动补
    # （补就是替人写清单）。
    if "required" in config and mapping is not None:
        entry = _entry_name(mapping, result)
        # `entry` 可写成 glob（如 `*.py`），那时没有单一入口名可查，跳过
        if entry and not any(c in entry for c in "*?["):
            if entry not in _allowed_root_names(mapping, result):
                notes.append(
                    f"⚠ 区文档声明了 `required`，但清单里没有入口文件 `{entry}` —— "
                    f"`required` 一旦声明就只查列出的项，入口会失去「缺必需文件」的保护。把 `{entry}` 加进 `required`")

    return result


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
        notes.append(
            f"⚠ 区文档里没有 `profile` 行，按默认 {DEFAULT_PROFILE} 审 —— "
            f"可在 {AREA_SUMMARY} 里补一行 `` - `profile` = `poly-version` ``"
        )
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
        print("映射：区文档里没有映射行（本 profile 不靠映射行定位文件）")
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

    # ── 区根文档（单独一块）────────────────────────────────────────
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

# 生成节的**结束**边界。拼回区文档时，「从 EMIT_HEADER 到这一行」整段替换掉旧的
# 「一、目录与文件树」节；这一行之后的其余各节原样保留。
#
# 为什么生成物要自带这条线：旧说明让人「切到标记与它之后第一个独立成行的 `---`
# 之间」，但**区文档里根本没有这种 `---`**（实测三个区文档 `grep -c '^---$'` 全为 0），
# 生成物自己也不产 —— 照做会一直吞到文件末尾，毁掉其余各节。
EMIT_FOOTER = "<!-- 本节结束 -->"


def _display_width(s: str) -> int:
    """终端显示宽度：CJK 与全角标点按 2 列算，其余按 1 列。"""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in s)


def _pad(s: str, width: int) -> str:
    """按显示宽度左对齐补空格，让 `←` 在同一列。"""
    return s + " " * max(1, width - _display_width(s))


def _tree_rows(profile: Profile, mapping: dict[str, str]) -> list[tuple[int, str]]:
    """把 AREA_FILES + SPEC 摊平成 (缩进级, 文本)；级 0 = 区根，级 1 = vNN/ 内，级 2 = 目录内。

    有映射时展开占位符（树里直接显示 `SingletonDemoExperiment.java` 这类真实文件名），
    这样重跑 --emit-spec 能原样重现文档里的树，不会悄悄退回占位符写法。
    """
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
        # 同级里后面还有没有同级的行
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
    out.append(
        f"本区用 **`{profile.title}`** 这套 profile —— {profile.intro}"
        "（换 profile 要重跑 `--emit-spec --profile <名>` 覆盖本节，不要手改。）"
    )
    out.append("")
    out.append(f"- `profile` = `{profile.title}`")
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
        f"`{AREA_SUMMARY}` 一份里分四块：目录规范（本节）、"
        "版本→风格映射总表与各版状态（原 `PLAN.md`）、"
        "各版实际产出与取舍（原每版 `MANIFEST.md`）、横向结论（原 `REPORT.md`）。"
        "**信息总量不该缩水，只是从四份分散变成一份分节。**"
    )
    out.append("")
    out.append(
        "> 少写文档 ≠ 少记信息。版本内没有文件清单时，最容易丢的是"
        "「这版为什么多/少一个文件」——那份解释现在归区根总结的版本小节。"
    )
    out.append("")
    return out


def _footer_notes() -> list[str]:
    """两个 builder 共用的收尾：本规范不管代码怎么写。"""
    return [
        "> 各版本的抽象方式、模块拆分、命名细节**不受本规范约束** —— 那正是风格差异的体现。",
        "> 本规范只管「放在哪、叫什么」，不管「怎么写」。",
        "",
    ]

def build_poly_version_section(area_name: str, mapping: dict[str, str],
                               profile: Profile = POLY_VERSION) -> str:
    """poly-version profile 的规范节。

    `profile` 必须是**解析过配置行之后**的那份（`_apply_config` 的产物）——
    生成节里的必需清单、交付用词都得跟审计实际执行的规则一致。
    """
    out: list[str] = _section_head(area_name, profile, mapping)
    out.extend(_mapping_block(mapping))
    out.extend(_required_tables(profile, mapping))

    src_dir = _expand("src", mapping)
    out.append(f"**`{src_dir}/` 内部不受约束**（本 profile 的要点）")
    out.append("")
    out.append(
        f"版本根**只锁 `{src_dir}/` 这一项**：里面有几个子目录、几个源文件、怎么分包，"
        "一律自定、审计不看。本规范只管「放在哪、叫什么」，不管「怎么写」。"
    )
    out.append("")

    out.append("**禁止**")
    out.append("")
    fixed = "、".join(
        f"`{_expand(_posix(t), mapping)}`"
        for t, req, _ in profile.spec if req and "/" not in t
    )
    # 编号动态排，改条目时不用同步序号
    rules: list[str] = [
        f"禁止改 {fixed} 这几个名字，也禁止把入口改名。"
        "「顶层不许多放文件」指源文件与改名 —— 上表列出的产物都是许可的。"
        if fixed else
        "禁止把入口改名。「顶层不许多放文件」指源文件与改名 —— 上表列出的产物都是许可的。",
    ]
    # 这两条只在区文档**声明了**对应产物时才写：`required` 一旦覆盖，
    # 未声明的产物就不在审计范围内，再列出来就是把规则指向不存在的文件，
    # 而「多出顶层文件」还会把它判成违规（见 `_top_level_strays`）。
    declared = {_expand(_posix(t), mapping) for t, _, _ in profile.spec}
    raw_templates = {t for t, _, _ in profile.spec}
    if "run_output.txt" in declared:
        rules.append("禁止手写或编辑 `run_output.txt` —— 必须由程序运行重定向产生，改过即作废。")
    if any(g.lower().endswith(".docx") for _, g in profile.glob_required) \
            or any(t.lower().endswith(".docx") for t in raw_templates):
        rules.append("禁止把报告 docx 放进子目录，它必须在版本根目录。")
    rules.append(f"禁止在版本目录里另立任何 md —— 文档只有区根一份 `{AREA_SUMMARY}`。")
    for i, rule in enumerate(rules, 1):
        out.append(f"{i}. {rule}")
    out.append("")

    # ── 交付源码的用词限制（由 JAVA_FORBIDDEN_* 派生，勿手抄到别处）──
    # 词表是 Java 课程场景的（中文风格名/设计模式名/文档简称），且 `java_checks = off`
    # 会把整个词表清空。空词表还照抄这三条，就是在给一个**审计根本不查**的规则
    # 写规范文字 —— 按 `java_checks` 的实际状态生成，别只按 profile。
    words = profile.java_forbidden_words
    if words:
        out.append("**交付源码里不得出现这些词**（硬性）")
        out.append("")
        out.append(
            "各版是**同一目标的若干替补方案，每版都要能当独立的人写的东西交出去**。所以交付源码里"
            "不得留下横向对照的内部概念 —— 一旦出现，读代码的人立刻能看出这是同一批人的"
            "多版本实验，「雷同双方记 0 分」就是要防这个。禁止三类："
        )
        out.append("")
        # 三类按位置取；词表不足两段时只生成存在的那些，避免 IndexError / 空条目
        style, mode, doc_word = words[1:4], words[4:], words[0]
        if style:
            out.append(
                "1. **版本代号与风格名**：" + "、".join(f"`{w}`" for w in style)
                + "；以及 `v01`、`v04` 这类版本号（版本号只存在于区根 "
                + f"`{AREA_SUMMARY}` 里）。"
            )
        if mode:
            out.append(
                "2. **设计模式名**：" + "、".join(f"`{w}`" for w in mode)
                + "。写代码的人不会在文件头先给自己贴流派标签，贴了就像在交「对照实验的第 N 组」。"
                "结构本身留着没问题，**只是别无中生有地自我命名**。"
            )
        if doc_word:
            out.append(
                "3. **本项目文档的规则简称**：`" + doc_word + "`（含 `"
                + doc_word + " 4.1` 这类带编号的引用）。"
                "要说「不得共用归并」就直接说事，别点名规则出处 —— 读者看不到那份文档，"
                "只会觉得作者在跟某个他没见过的规范对齐。"
            )
        out.append("")
    if profile.java_header_command_check:
        out.append(
            "另外禁止在**文件头**抄「编译 / 运行」命令行（形如 `编译：javac …`、"
            "`运行：java -Dstdout.encoding=…`）—— 那属于 `README.txt` 的职责，"
            "夹在文件头注释里像 README 摘抄。**行内**提到 `javac` 不算违规"
            "（例如注释里说某写法会多一次编译），只查文件头部的独立命令行。"
        )
        out.append("")
    if words:
        out.append(
            "> **例外**：「实验一 合并排序」不算禁用词 —— 它就是实验题目，报告标题与 README 都要用。"
        )
        out.append("")

    out.extend(_doc_layer_block())

    # ── 编译与运行约定（唯一真源在 check_code.py，勿手抄到别处）──
    if profile.code_checks:
        out.append("## 二、编译与运行（硬性）")
        out.append("")
        out.append(build_run_contract(area_name=area_name))

    out.extend(_footer_notes())
    return "\n".join(out)



def build_section(area_name: str, mapping: dict[str, str], profile: Profile) -> str:
    """按 profile 生成区根文档里那一节规范，含首尾边界标记。

    `profile` 原样传给两个 builder —— 它必须是配置行解析后的那份，
    否则生成节会按 profile 缺省值写（如 150 行），与审计实际执行的规则对不上。
    """
    body = build_poly_version_section(area_name, mapping, profile)
    return f"{body}\n{EMIT_FOOTER}"


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
    print(f"  切法是首行标记到末行 `{EMIT_FOOTER}` —— 生成物自带首尾边界，"
          "不必去找区文档里的 `---`（那种行本来就不存在）。")
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
                    help="版本区目录，如 SingletonPattern/poly-singleton-demo")
    ap.add_argument("--emit-spec", action="store_true",
                    help="生成区根文档里的规范节 markdown，而不是审计")
    ap.add_argument("-o", "--out", type=Path, default=None,
                    help="配合 --emit-spec：写到文件（不给则打到 stdout）")
    ap.add_argument("--profile", default=None,
                    help=f"指定 profile（{'、'.join(sorted(PROFILES))}）；"
                         "不给则读区文档里的 `profile` 行")
    ap.add_argument("--only", default=None,
                    help="只审计某一个版本，如 --only v03")
    args = ap.parse_args(argv)

    _setup_stdout()

    area_root: Path = args.version_area
    if not area_root.is_dir():
        print(f"× 目录不存在：{_posix(area_root)}")
        return 1

    if args.emit_spec:
        # `--only` 只对审计有意义。传了就明说被忽略，
        # 不要静默吞掉 —— 静默会让人以为那面旗子起了作用。
        if args.only:
            print("⚠ --only 对 --emit-spec 无意义，本次忽略")
        profile, mapping, notes = _resolve_profile(area_root, args.profile)
        for n in notes:
            print(n)
        return cmd_emit(area_root, mapping, profile, args.out)

    return cmd_audit(area_root, args.only, args.profile)


if __name__ == "__main__":
    sys.exit(main())
