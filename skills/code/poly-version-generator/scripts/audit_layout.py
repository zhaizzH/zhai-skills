#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""poly-version-generator 的目录规范：唯一真源 + 审计器 + 规范节生成器。

本文件是「n 个对照版本产出到哪、叫什么名字」的**唯一真源**。
其它地方（SKILL.md 的说明、各区 `项目总结.md` 的规范节）都从这里派生，
不要再手抄一份树 —— 手抄的那份一定会漂。

# 两套 profile

区自己在区根文档里声明用哪套（一行 `` - `profile` = `<名>` ``）。两套的规矩不同，
因为「什么算违规」本来就取决于「版本是什么」：

  single-file      一个目标 N 种风格**各写一遍**，代码是实现物。
                   → 锁单文件、行数上限、交付用词、区根 `提交/` 每版一份。
  source-snapshot  同一既有项目 N 种风格**各改一遍**，每版是完整源码快照。
                   → 只锁 `src/`，`src/` 内部一律不管，IDE 元数据一律不管。

快照型下**不做**单文件/行数/交付用词/README/`提交/` 这几类检查 —— 不是因为
「快照区可以糊弄」，而是因为那几条的**前提在快照型下不成立**：

  · 快照是已冻结的物料，本就分包多文件（原项目十几个 `.java`），「实现必须单文件」无意义；
  · 快照逐字复制自原分支，**不许就地改**，所以「改掉违规用词」这个动作本身被禁止；
  · 交付用词检查会误伤：「契约」在中文源码里是**普通词**（接口约定），不是本项目
    `CONTRACT.md` 的简称专属；而子串检查分不出这两种用法，所以快照型一律不跑它。

一句话：规范只管「放在哪、叫什么」，不管「怎么写」；而**管不管得着「怎么写」，
由 profile 定**。

# 四种用法（审计 / 单版审计 / 生成规范节 / 临时指定 profile）

    # 审计：逐个版本比对实际文件与 SPEC，输出 PASS/FAIL 表
    python audit_layout.py SingletonPattern/poly-singleton-demo

    # 只审一个版本
    python audit_layout.py SingletonPattern/poly-singleton-demo --only v03

    # 生成区根文档里那一节规范（第一次建版本区时做一次；树变了再生成一次）
    python audit_layout.py SingletonPattern/poly-singleton-demo --emit-spec -o spec.md
    python audit_layout.py SingletonPattern/poly-singleton --emit-spec --profile source-snapshot

    # 文档里没写 profile 行时，用 --profile 临时指定（例如手写第一节的老区）
    python audit_layout.py PrototypePattern/poly-prototype-shallow --profile source-snapshot

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
#     `profile`   = `source-snapshot`      → profile 选择
#     `<Xxx>`     = `SingletonDemo`        → 占位符映射（带尖括号）
#     其它标识符   = 值                     → 配置覆盖（见 CONFIG_KEYS）
#
# 这是对旧 MAPPING_RE / PROFILE_RE 的收口：两者的既有行为都被包含，
# 所以**旧区文档的解析结果逐字不变**。
#
# 三点比「一对反引号夹一个值」更宽，都是被清单键逼出来的（见 CONFIG_LIST_KEYS）：
#
#   1. 值可空 —— 文档说 `submit` **留空 = 本区不生成提交包**，而 `` `submit` = `` ``
#      （两个反引号之间什么都没有）在原来的 `[^`]+` 下**根本匹配不到**，于是那一行
#      被整个丢弃、`submit` 保持缺省的 5 项 —— 「声明为空」静默失效。
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
#   max_lines   每个源文件的物理行上限；`0` = 不限。覆盖 JAVA_MAX_LINES。
#   required    版本根必需项，逗号分隔（可含占位符）。只列这些，不在列的**不检查**。
#   submit      提交包清单，逗号分隔；空串 = 本区不生成提交包。
#
# 两个清单键都接受**每个值各加一对反引号**的写法（多行或同一行都行）：
#
#     - `required` = `main.py`, `_pack.py`
#
# `CONFIG_RE` 一次只收一对反引号，故 `_classify_config` 按出现次序合并同名清单键 ——
# 先转 dict 会静默丢掉第二项。只有清单键合并，其余键仍取末值。
#   java_checks `on`/`off`：交付用词与「头部编译运行命令」检查。
CONFIG_KEYS: tuple[str, ...] = (
    "entry", "max_lines", "required", "submit", "java_checks",
)

# 其中「值是逗号分隔清单」的键。它们的自然写法是**每个值各自加一对反引号**：
#
#     - `required` = `main.py`, `_pack.py`
#
# 而 `CONFIG_RE` 只认「一对反引号夹键 = 一对反引号夹值」，于是这条行只会读出
# `('required', 'main.py')` —— `_pack.py` 静默丢失。所以这几个键要按**出现次序合并**，
# 不能像标量键那样取末值（见 `_classify_config`）。
CONFIG_LIST_KEYS: tuple[str, ...] = ("required", "submit")

# 打包入口脚本的约定名。规范节的提交段与审计提示都按这个名字说「跑 python _pack.py」，
# 但 `required` 一旦声明就只认列出的项 —— 冲突时见 `_packer_permitted` 与 `_apply_config`
# 末尾的自洽性检查。
PACKER_NAME = "_pack.py"

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
    "Desktop.ini", "Thumbs.db",
]


# ══════════════════════════════════════════════════════════════════════
# 二、profile 定义 —— 改这里，对应那一类版本区全跟着变
# ══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Profile:
    """一套版本区规矩。

    `spec` 是版本目录内的条目表，形状与旧版一致：每条 = (相对 vNN/ 的路径, 必需?, 说明)。
    含 "/" 且结尾是 "/" 的是目录；`glob_required` 里的路径按通配匹配（见 _check_glob_required）；
    其余是文件。说明会原样写进规范节的表格里，用祈使句、说清为什么。
    """

    key: str
    title: str
    intro: str
    spec: tuple[tuple[str, bool, str], ...]
    # 入口文件名模式（可含占位符，如 `<Xxx>Experiment.java`）。空 = 沿用
    # 「`<Xxx>Experiment.java`」这一 Java 约定；区文档的 `entry` 配置行可覆盖。
    # 换语言时改这一个键即可，不必动脚本。
    entry: str = ""
    # 通配必需项：路径 → glob。用于名字由映射行指派的必需品，如 ("<报告名>", "*.docx")。
    glob_required: tuple[tuple[str, str], ...] = ()
    # 区根 `提交/`（每版一份交付包）；空元组 = 本 profile 不生成提交包
    submit_files: tuple[tuple[str, str], ...] = ()
    # 单个 .java 的物理行数上限；None = 不设上限
    java_max_lines: int | None = None
    # 是否强制「代码实现必须单文件 + 入口名固定」。这是**核心约束**，
    # 与行数上限分开：配置行能把 `max_lines` 设成 0 取消行数限制，
    # 但取消不了这一条 —— 它才是「single-file」这个 profile 的定义。
    enforce_single_file: bool = False
    # 允许存在的额外 .java 名（入口文件由映射行的 <Xxx> 指派）
    java_allowed_extra: frozenset[str] = frozenset()
    # 交付源码禁用词与「文件头禁抄编译/运行命令」
    java_forbidden_words: tuple[str, ...] = ()
    java_forbidden_re: re.Pattern[str] | None = None
    java_header_command_check: bool = False
    # README.txt 里不得出现的开发侧名字；None = 本 profile 不查 README
    readme_forbidden: tuple[str, ...] | None = None
    # 版本根允许出现、但不写进 SPEC 的文件后缀
    allowed_root_suffixes: frozenset[str] = frozenset()
    # 「多出顶层文件」的提示语（各 profile 的落点不同）
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
# ⚠️ 本类检查**只在 `single-file` profile 下运行**。快照型下源码是冻结物料，
# 不许就地改，且「契约」等词本就可能出现在原项目的正常中文里 —— 见本文件头部说明。
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

# 每个 .java 的**物理行数**上限（含注释与空行，即 `wc -l` 的数）。
# 用户的硬性要求：五个方案代码都不要超过 150 行。口径是物理行，不是代码行 ——
# 所以注释与空行也占额度，注释必须写得克制。
# 这条与「单文件」是一对：单文件管「不许拆成几个文件」，行数上限管「不许写长」，
# 两者共同逼出「同一文件内组织方式的差异」，而不是靠规模堆砌拉开区别。
JAVA_MAX_LINES = 150

# README.txt 里**不得出现**的开发侧名字。README 是交付说明，会被 `_pack.py` 逐字复制进
# 区根 `提交/`，而提交包里没有区根总结、也没有 `report/` 与 `test/` ——
# 在 README 里列这些名字，到了提交包就成了指向不存在文件的悬空引用。
# 这类过期文案 `verify_report.py`（只查数字可溯源）和布局检查**都抓不到**，
# 只能靠这条子串检查兜住。
README_FORBIDDEN: tuple[str, ...] = (
    "MANIFEST", "项目总结", "_make_report", "report/", "test/",
    "verify_counts", "verify_report", "audit_layout",
)

# ── profile ①：单文件实现型 ──────────────────────────────────────────
SINGLE_FILE = Profile(
    key="single-file",
    title="single-file",
    intro="一个目标 N 种风格**各写一遍**，代码是实现物，故约束单文件与行数。",
    spec=(
        # ---- 版本根目录的固定文件 ----
        ("<Xxx>Experiment.java", True,
         "课程提交用源程序。名固定（`<Xxx>` 由本区的映射行指派），跨版本 `diff` 的锚点"),
        ("Screenshot.java", True, "截图工具。名固定，各版一致，不做变体"),
        ("run_output.txt", True,
         "程序真实输出，由 stdout 重定向产生；**禁手写、禁编辑**，改过即作废"),
        ("README.txt", True,
         "**交付说明**：文件说明 + 编译运行方法。只许描述提交包里的那几个文件 —— "
         "它会被 `_pack.py` 逐字复制进区根 `提交/`，提到区根总结/`report/`/`test/` "
         "就成了指向不存在文件的悬空引用（本脚本会查，见 `README_FORBIDDEN`）"),
        ("_make_report.py", True, "报告生成入口。放版本根目录，便于跨版对照"),
        ("_pack.py", True,
         "打包入口：把本版交付物复制到区根 `提交/`。与 `_make_report.py` 同理放版本根，"
         "各版同名以便跨版对照"),
        # `<报告名>` 按约定是**含扩展名的完整文件名**（如 `实验一 合并排序.docx`），
        # 故这里不再补 .docx —— 补了会变成 `…….docx.docx`
        ("<报告名>", True,
         "生成的报告，**必须在版本根目录**（不是子目录），便于统一打包；"
         "`<报告名>` 含扩展名，由映射行指派"),

        # ---- 报告层：目录与三个文件名都固定 ----
        ("report/", True,
         "报告与解析的 Python 层。**目录及内部三个文件名都固定** —— 技能存在的前提是"
         "「不同人的同名文件能直接对照」，各版另起名字则 `diff` 无从下手。"
         "层内怎么抽象、拆几个函数、是否再分文件，各版自定"),
        ("report/parse.py", True, "解析 `run_output.txt`，登记成事实表"),
        ("report/facts.py", True, "事实表 / 数据模型定义"),
        ("report/render.py", True, "排版组织：把事实表渲染成文档"),

        # ---- 弹性区：可自由增删，风格差异的落点 ----
        ("test/", False,
         "校验脚本（计数比对、输出结构完整性等）。**可自由增删**"),
    ),
    glob_required=(("<报告名>", "*.docx"),),
    submit_files=(
        ("<Xxx>Experiment.java", "入口源程序（单文件）"),
        ("Screenshot.java", "截图工具"),
        ("run_output.txt", "程序真实输出，由 stdout 重定向产生"),
        ("README.txt", "交付说明，由 `_pack.py` 从版本根**逐字复制**而来"),
        ("<报告名>", "报告 docx"),
    ),
    java_max_lines=JAVA_MAX_LINES,
    enforce_single_file=True,
    java_allowed_extra=frozenset({"Screenshot.java"}),
    java_forbidden_words=JAVA_FORBIDDEN_WORDS,
    java_forbidden_re=JAVA_FORBIDDEN_RE,
    java_header_command_check=True,
    readme_forbidden=README_FORBIDDEN,
    allowed_root_suffixes=frozenset({".docx"}),
    stray_hint="校验脚本放 test/",
)

# ── profile ②：源码快照型 ───────────────────────────────────────────
#
# 每版是既有项目的**完整源码快照**，只锁 `src/`。
#
# 为什么**不**把 `.iml` 列进版本根的必需项（曾经列过，2026-09-22 撤掉）：
#
#  1. 它是 IDE 元数据，不是版本产物。用户定：**版本区不收录 IDEA 文件**。
#  2. 它其实是**可推导的**，锁它并不能换来「每版能独立编译运行」——
#     各区 `.iml` 都是同一份样板（只有 `$MODULE_DIR$/src` 一个 sourceFolder，
#     不依赖兄弟版本），所以某版临时缺了，从任一版复制一份、或让 IDE 重认
#     source root 即可。重跑与截图从来就不缺依据 —— 原项目本来就怎么跑，
#     版本区照旧怎么跑，不必靠 `vNN/` 里的 `.iml`。
#  3. 逐版改名（`v01.iml`…`v05.iml`）与五版同名都出现过，锁名字等于把
#     「实验语义」写进布局规范。
#
# 结果：本 profile 只认 `src/` —— 而这正是快照区真正的交付物，也是唯一
# 能证明「这几版是同一物料的若干写法」的东西。
SNAPSHOT = Profile(
    key="source-snapshot",
    title="source-snapshot",
    intro="同一既有项目 N 种风格**各改一遍**，每版是完整源码快照，故只锁 `src/`。",
    spec=(
        ("src/", True,
         "该分支的完整源码快照，**照抄原项目的包结构**。本 profile 只锁 `src/`，"
         "内部有几个包、几个 `.java` 一律不管；IDE 元数据（`.iml`/`.idea/`）不收录"),
    ),
    glob_required=(),
    submit_files=(),
    java_max_lines=None,
    java_allowed_extra=frozenset(),
    java_forbidden_words=(),
    java_forbidden_re=None,
    java_header_command_check=False,
    readme_forbidden=None,
    allowed_root_suffixes=frozenset(),
    stray_hint="版本根只该有 src/（IDE 文件不入库）",
)

PROFILES: dict[str, Profile] = {p.key: p for p in (SINGLE_FILE, SNAPSHOT)}
DEFAULT_PROFILE = SINGLE_FILE.key

# 区根共享文件：n 个版本共有，版本目录里不得出现同名文件
AREA_FILES: tuple[tuple[str, str], ...] = (
    (AREA_SUMMARY, "区根**唯一一份**文档：规范节 + 版本→风格映射 + 各版状态 + 横向结论"),
)


def _submit_files(profile: Profile) -> tuple[tuple[str, str], ...]:
    """本 profile 的交付清单；不生成提交包的 profile 返回空元组。

    用空元组而不是 None 表达「没有提交包」：调用方不必到处判空，
    「有没有」只用一个真假判断就够。
    """
    return profile.submit_files


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
    `` `required` = `main.py`, `_pack.py` `` 读成两个同键对子；就算值写在一个反引号对里
    （`main.py, _pack.py`），分成两行写也还是同键两处。先转成 `dict` 会按同名键覆盖，
    静默丢掉后面那些值。这里按**出现次序**分组，再由下面的规则决定合并还是取末值。

    | 键 | 同名重复时 |
    |---|---|
    | `CONFIG_LIST_KEYS`（`required`/`submit`） | **按次序合并**（值内去重） |
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

        - `profile` = `source-snapshot`
        - `<Xxx>` = `SingletonDemo`
        - `<报告名>` = `实验 单例模式演示.docx`
        - `max_lines` = `260`          ← 可选，覆盖 profile 的缺省

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


def submit_file_names(mapping: dict[str, str], profile: Profile) -> list[str]:
    """区根 `提交/` 里应有的文件名（占位符按映射展开）。"""
    return [Path(_expand(t, mapping)).name for t, _ in _submit_files(profile)]


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

    `profile.entry` 优先；没写则退回 Java 约定 `<Xxx>Experiment.java`。
    两者都不可用时返回 None（只有目录、没有入口名的情况）。
    """
    tmpl = profile.entry or ("<Xxx>Experiment.java" if "Xxx" in mapping else "")
    if not tmpl:
        return None
    return Path(_expand(tmpl, mapping)).name


def _allowed_java_names(mapping: dict[str, str], profile: Profile) -> set[str]:
    """本规范允许存在的 .java 文件名（不含路径）。"""
    allowed = set(profile.java_allowed_extra)
    if "Xxx" in mapping:
        allowed.add(f"{mapping['Xxx']}Experiment.java")
    entry = _entry_name(mapping, profile)
    if entry and entry.endswith(".java"):
        allowed.add(entry)
    return allowed


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
    """版本根允许出现的目录名（弹性区 + 必需目录）。"""
    allowed: set[str] = set()
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

def _java_line_count(p: Path) -> int:
    """.java 的物理行数（与 `wc -l` 一致：以换行为准，末尾无换行则不计最后一行）。"""
    return len(p.read_text(encoding="utf-8", errors="replace").split("\n")) - 1


def _check_glob_required(version_dir: Path, tmpl: str, glob: str,
                         mapping: dict[str, str], why: str) -> list[str]:
    """通配必需项：版本根下按 glob 找，数量必须恰为 1；给了映射还要名字对得上。

    用于 `<报告名>`（`*.docx`）这类 —— 名字由映射行指派，不适合在 SPEC 里写死。
    """
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
    # 文档只有区根那一份。已取消的每版 MANIFEST.md 由 4.6 统一报（它同时是
    # 「多出的顶层文件」），这里不重复报 —— 同一条问题报两遍只会让人以为有两处要改。
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
            continue                      # 无映射：只查目录，不查具体名
        expanded = _expand(tmpl, mapping)
        if not (version_dir / expanded).is_file():
            problems.append(f"缺必需文件 {_posix(expanded)}")

    # ── 4.3 入口文件不得改名（仅单文件型，Java 惯例）──────────────
    # 保留原始的 Java 专用判断：入口缺席/写错的兜底在 4.4a（按 `entry` 判，
    # 覆盖非 Java 区）。这里只报「有 .java 却没一个是入口名」的改名情形。
    if profile.enforce_single_file and "Xxx" in mapping:
        want = f"{mapping['Xxx']}Experiment.java"
        java_top = [p.name for p in _actual_files(version_dir)
                    if "/" not in p.as_posix() and p.name.endswith(".java")]
        if java_top and want not in java_top:
            problems.append(
                f"入口文件被改名：期望 {want}，版本根实际有 {'、'.join(java_top)}"
            )

    # ── 4.4 代码实现必须单文件（仅单文件型）───────────────────────
    # 注意：这里扫的是**递归**的全部 .java，不只是顶层。若只查顶层，
    # 把辅助类塞进 src/ 或 java/ 这类子目录就能绕过「单文件」约束。
    if profile.enforce_single_file:
        allowed_java = _allowed_java_names(mapping, profile)
        extra_java = [p for p in _actual_files(version_dir)
                      if p.name.endswith(".java") and p.name not in allowed_java]
        for p in extra_java:
            problems.append(
                f"多出 Java 源文件 {_posix(p)} —— 代码实现必须单文件，"
                f"只允许 {('、'.join(sorted(allowed_java))) or '入口文件'}，"
                "实现差异靠同一个文件内部的写法体现"
            )

        # ── 4.4a 行数上限 ─────────────────────────────────────────
        # `max_lines` 可被配置行设成 0 取消（彼时 java_max_lines=None）。
        #
        # 口径按**入口文件**（`profile.entry`，缺省为 Java 入口）而不是「所有 .java」：
        # 行数上限要能跟着语言走 —— 非 Java 区没有 .java，只按 .java 过滤等于永不生效。
        if profile.java_max_lines is not None:
            # 检查「入口 + profile 允许的额外文件」：Java 下即 `<Xxx>Experiment.java`
            # 与 `Screenshot.java`（与改造前逐字一致），非 Java 下即入口本身。
            counted = allowed_java | ({_entry_name(mapping, profile)} - {None})
            # `entry` 是**模式**（可含占位符、可写成 glob），不一定是字面文件名：
            # 写 `entry` = `*.py` 时入口名解不出来，上面的集合就只剩 Screenshot.java，
            # 行数上限被**静默**架空（实测 50 行文件、上限 3 行仍判 PASS）。
            # 单个不含通配符的 `entry` 已经进 counted，这里只补「模式没落到任何实际文件」
            # 的情况 —— 那等于入口文件缺失，按缺入口报，别让它悄悄跳过行数检查。
            entry_tmpl = profile.entry or ("<Xxx>Experiment.java" if "Xxx" in mapping else "")
            # 4.3 已经报过「入口改名」时不再报第二条 —— 同一个原因不说两遍
            if entry_tmpl and not any("入口文件" in p for p in problems):
                entry_expanded = _expand(_posix(entry_tmpl), mapping)
                files = _actual_files(version_dir)
                if any(ch in entry_expanded for ch in "*?["):
                    # 模式：把匹配到的文件都算作入口。文档把 `entry` 写作 glob 是允许的,
                    # 那就得按 glob 收口，「模式没落下任何文件」才算缺入口。
                    matched = [p for p in files
                               if fnmatch.fnmatch(p.name, Path(entry_expanded).name)]
                    if not matched:
                        problems.append(
                            f"入口文件 `{entry_expanded}` 匹配不到任何文件（区文档 `entry` 指定）"
                            "—— 行数上限只查入口，入口不在就无从生效"
                        )
                    counted |= {p.name for p in matched}
                elif not any(p.name == Path(entry_expanded).name for p in files):
                    problems.append(
                        f"入口文件 {entry_expanded} 不存在（区文档 `entry` 指定）—— "
                        "行数上限只查入口，入口不在就无从生效"
                    )
            for p in sorted(_actual_files(version_dir)):
                if p.name not in counted:
                    continue
                n = _java_line_count(version_dir / p)
                if n > profile.java_max_lines:
                    problems.append(
                        f"{_posix(p)} 有 {n} 行，超出上限 {profile.java_max_lines} 行"
                        f"（按物理行计，含注释与空行）—— 精简实现，不是删注释硬凑"
                    )

        # ── 4.4b 交付源码里不得有横向对照的内部概念 ───────────────
        for p in sorted(_actual_files(version_dir)):
            if p.name not in allowed_java:
                continue
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

    # ── 4.7 README.txt 必须是交付说明（仅单文件型）────────────────
    # README 会被 _pack.py 逐字复制进提交包，但提交包里没有区根总结、也没有
    # report/ 与 test/ —— 于是版本区里那些「完整文件清单 + 重跑步骤」到了提交包
    # 就成了指向不存在文件的悬空引用，读者会以为少了文件。
    if profile.readme_forbidden is not None:
        readme = version_dir / "README.txt"
        if readme.is_file():
            text = readme.read_text(encoding="utf-8", errors="replace")
            hits = [w for w in profile.readme_forbidden if w in text]
            if hits:
                problems.append(
                    f"README.txt 里出现了开发侧的名字 {'、'.join(hits)} —— "
                    "README 是**交付说明**，会被 _pack.py 逐字复制进区根 `提交/`，"
                    f"而提交包里没有区根 {AREA_SUMMARY} 与 report/、test/。"
                    f"删掉指向它们的句子（完整文件清单与重跑步骤属于区根 {AREA_SUMMARY}）"
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


def audit_submission(area_root: Path, mapping: dict[str, str],
                     versions: list[Path], profile: Profile) -> dict[str, list[str]]:
    """审计区根 `提交/`：每个版本一个子目录，各自恰为 SUBMIT_FILES 那几个文件。

    返回 {版本名: [问题...]}。`提交/` 不存在不算错（还没打包时本就不该有），
    此时返回空 dict。只报错，不自动修正：多出来的文件也可能是别的东西，删不删由人判断。
    """
    submit = area_root / SUBMIT_DIR
    if not submit.is_dir():
        return {}

    want = submit_file_names(mapping, profile)
    result: dict[str, list[str]] = {}

    # 提交包只该装版本名目录，别的顶层条目都是混进来的
    known = {v.name for v in versions}
    for p in sorted(submit.iterdir()):
        if p.is_dir():
            if p.name not in known:
                result.setdefault(p.name, []).append(
                    f"提交包目录名 {p.name}/ 不是版本名 —— `{SUBMIT_DIR}/` 下只该有 "
                    f"{'、'.join(sorted(known))} 这样的版本名目录"
                )
            continue
        if _is_ignored(Path(p.name)):
            continue
        result.setdefault(SUBMIT_DIR, []).append(
            f"`{SUBMIT_DIR}/` 顶层不该有文件 {p.name} —— 交付物要放进 "
            f"`{SUBMIT_DIR}/<版本名>/` 里（每个版本一个目录）"
        )

    for v in versions:
        pkg = submit / v.name
        if not pkg.is_dir():
            # 修法指引只在真的允许 `_pack.py` 时给 —— 没列在 `required` 里的区，
            # 「跑 python _pack.py」这句本身就是让人踩「多出顶层文件」FAIL 的坑。
            how = (f"在本版目录下跑 python {PACKER_NAME} 生成"
                   if _packer_permitted(profile, mapping)
                   else f"按 `submit` 清单把文件挑进 {SUBMIT_DIR}/{v.name}/")
            result.setdefault(v.name, []).append(
                f"缺 {SUBMIT_DIR}/{v.name}/ —— {how}"
            )
            continue
        problems = result.setdefault(v.name, [])
        actual: set[str] = set()
        for p in sorted(pkg.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(pkg)
            if _is_ignored(rel):              # 截图/、*.class、~$* 等产物一律不算
                continue
            name = rel.as_posix()
            actual.add(name)
            if "/" in name:
                problems.append(
                    f"提交包里不该有子目录 {name} —— 提交包是平铺的 "
                    f"{len(want)} 个文件，开发文件（report/、test/）不得混入"
                )
            elif name not in want:
                problems.append(
                    f"提交包里多出文件 {name}（不在交付清单内；"
                    "提交包只放入口源程序、Screenshot.java、run_output.txt、README.txt、报告 docx）"
                )
        for name in want:
            if name not in actual:
                how = (f"在本版目录下跑 python {PACKER_NAME} 重新生成"
                       if _packer_permitted(profile, mapping)
                       else f"从版本目录里把它复制进 {SUBMIT_DIR}/{v.name}/")
                problems.append(f"提交包缺文件 {name} —— {how}")

    # 每个版本先占一个空列表位，好让问题按版本归组；这里把没问题的版本滤掉，
    # 返回空 dict 才代表「全 PASS」（调用方就是按真假判断的）
    return {name: problems for name, problems in result.items() if problems}


SUBMIT_DIR = "提交"


def find_versions(area_root: Path) -> list[Path]:
    """找出版本区里所有 `v数字` 形式的目录，按名字排序。"""
    if not area_root.is_dir():
        return []
    return sorted(p for p in area_root.iterdir()
                  if p.is_dir() and re.fullmatch(r"v\d+", p.name))


def _packer_permitted(profile: Profile, mapping: dict[str, str]) -> bool:
    """本区的规范是否**允许**版本根存在 `_pack.py`。

    规范节的提交段写着「跑 `python _pack.py`」（各版打包入口就在版本根），
    但 `required` 一旦声明就只认列出的项：没列 `_pack.py` 的区，照这句放一个
    `_pack.py` 会被 `_top_level_strays` 判成「多出顶层文件」—— 生成节与审计
    自相矛盾，照文档做反而 FAIL。所以判定必须与审计**同源**，不能各写一套。

    版本根放行什么，只看 `_allowed_root_names`（= `profile.spec` 展开后的顶层名）
    加 `glob_required` —— 这正是 `_top_level_strays` 用的那两个集合，这里直接复用。

    注意**不能**把 `profile.submit_files` 算进来：`submit` 管的是区根
    `提交/<版本名>/` 里该有哪些文件，那里的 `_pack.py` 合法，并不代表版本根也能放它。
    （`entry` 同理不算：它只是入口**名**，能不能落在版本根仍要 `required` 点头。）
    """
    if PACKER_NAME in _allowed_root_names(mapping, profile):
        return True
    return any(fnmatch.fnmatch(PACKER_NAME, g) for _, g in profile.glob_required)


def _apply_config(profile: Profile, config: dict[str, str],
                  notes: list[str], mapping: dict[str, str] | None = None) -> Profile:
    """把区文档里的配置覆盖应用到 profile 上，返回展开后的 profile。

    不写任何配置键时返回的 profile 与原对象**逐字段相等** —— 这是既有版本区
    零迁移的依据。只认 `CONFIG_KEYS` 里的键，未知键已被
    `_classify_config` 丢弃。

    `required` / `submit` 用「声明即替换」语义：一旦在区文档里写了，就**只检查**
    列出的那些文件，不在列的不再报「缺必需文件」。这是「核心 + 可配」的落点 ——
    入口单文件与行数上限仍由 profile 核心约束着，产物清单则交给各区自定。

    `mapping` 可选，只用于自洽性检查（见末尾）—— 不给就跳过那一条。
    """
    if not config:
        return profile

    changes: dict[str, object] = {}

    if "max_lines" in config:
        raw = config["max_lines"].strip()
        try:
            n = int(raw)
        except ValueError:
            raise SystemExit(f"× `max_lines` 要是整数，得到 `{raw}`")
        changes["java_max_lines"] = None if n <= 0 else n

    if "java_checks" in config:
        raw = config["java_checks"].strip().lower()
        if raw not in ("on", "off"):
            raise SystemExit(f"× `java_checks` 只能是 `on` 或 `off`，得到 `{raw}`")
        off = raw == "off"
        if off:
            changes["java_forbidden_words"] = ()
            changes["java_forbidden_re"] = None
            changes["java_header_command_check"] = False
            changes["readme_forbidden"] = None

    if "entry" in config:
        changes["entry"] = config["entry"].strip()

    if "required" in config:
        items = _split_config_list(config["required"])
        # 空清单是合法的：「本版没有任何必需产物」。
        # spec 的第三列是给人看的说明，配置行不给说明，故留空串。
        changes["spec"] = tuple((it, True, "") for it in items)
        changes["glob_required"] = ()
        notes.append(f"⚠ 区文档声明了 `required`，本次只检查这 {len(items)} 项")

    if "submit" in config:
        items = _split_config_list(config["submit"])
        changes["submit_files"] = tuple((it, "") for it in items)
        notes.append(
            f"⚠ 区文档声明了 `submit`（{len(items)} 项）"
            if items else "⚠ 区文档把 `submit` 声明为空，本区不生成提交包")

    result = dataclasses.replace(profile, **changes)

    # ── 配置自洽性：声明了提交包，却不允许打包入口存在 ──────────────
    # 规范节的提交段让人「cd 到版本目录跑 python _pack.py」，但 `required` 声明后
    # 只认列出的项 —— `_pack.py` 不在列就会被判成「多出顶层文件」。生成节与审计
    # 自相矛盾时，照文档做反而 FAIL，所以在这里点明，而不是静默改判。
    # （只报不自动修正：`required` 是「声明即替换」，替人往清单里塞文件正是本次
    #   要修的那类静默行为；且不改判 = 不改既有区的任何输出。）
    if result.submit_files and mapping is not None \
            and not _packer_permitted(result, mapping):
        notes.append(
            f"⚠ 区文档声明了 `submit`，但 `required` 里没有 `{PACKER_NAME}` —— "
            f"规范节说「跑 python {PACKER_NAME}」，可真放了它会报「多出顶层文件」。"
            f"把 `{PACKER_NAME}` 加进 `required`（或改用别的打包方式）")

    # ── 配置自洽性：`required` 替换了 spec，却没把入口文件列进去 ──────
    # `required` 是「声明即替换」：一旦写了，4.2 只查列出的项，入口不再计入必需。
    # 而 4.4a 仍会按 `entry`（缺省 Java 约定）查入口是否存在 —— 于是入口缺失与否
    # 取决于两处独立逻辑。若 `required` 没含入口名，入口就不受 4.2 保护，
    # 行数上限也会随之静默失去落点。这里点明，不自动补（补就是替人写清单）。
    if "required" in config and mapping is not None:
        entry = _entry_name(mapping, result)
        # `entry` 可写成 glob（如 `*.py`），那时没有单一入口名可查，跳过
        if entry and not any(c in entry for c in "*?["):
            if entry not in _allowed_root_names(mapping, result):
                notes.append(
                    f"⚠ 区文档声明了 `required`，但清单里没有入口文件 `{entry}` —— "
                    f"`required` 一旦声明就只查列出的项，入口会失去「缺必需文件」的保护，"
                    f"行数上限也无从生效。把 `{entry}` 加进 `required`")

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
            f"若是快照区，请在 {AREA_SUMMARY} 里补一行 "
            f"`` - `profile` = `source-snapshot` ``（或本次加 --profile source-snapshot）"
        )
    if doc is not None and doc.name != AREA_SUMMARY:
        notes.append(
            f"⚠ 映射行读自 {doc.name}（过渡期兼容）—— "
            f"区根现在只留一份 {AREA_SUMMARY}，请把内容并过去"
        )
    return _apply_config(profile, config, notes, mapping), mapping, notes


def cmd_audit(area_root: Path, only: str | None, check_submit: bool,
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
    elif profile.key == SNAPSHOT.key:
        print("映射：本 profile 不需要映射行（版本根只锁 src/）")
    else:
        print("映射：区文档里没有映射行，入口文件名按占位符模式跳过比对")
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

    # ── 区根提交包（单独一块，与上面逐版本表分开显示）────────────────
    if check_submit and _submit_files(profile):
        print()
        submit = area_root / SUBMIT_DIR
        if not submit.is_dir():
            # 同样按 `_packer_permitted` 分支：没声明 `_pack.py` 的区不该被告知去跑它
            hint = (f"各版打包后，cd 到版本目录跑 python {PACKER_NAME}"
                    if _packer_permitted(profile, mapping)
                    else "各版按 `submit` 清单挑好文件后放进来")
            print(f"– {SUBMIT_DIR}/  未生成（{hint}）")
        else:
            submit_problems = audit_submission(area_root, mapping, versions, profile)
            total += 1
            if not submit_problems:
                print(f"√ {SUBMIT_DIR}/  PASS（{len(versions)} 个版本，"
                      f"每份 {len(_submit_files(profile))} 个交付文件，无多余、无缺失）")
            else:
                failed += 1
                print(f"× {SUBMIT_DIR}/  FAIL")
                for name in sorted(submit_problems):
                    for p in submit_problems[name]:
                        print(f"    - {p}")
    elif check_submit and not _submit_files(profile):
        print()
        print(f"– {SUBMIT_DIR}/  本 profile（{profile.title}）不生成提交包，跳过")

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


def build_single_file_section(area_name: str, mapping: dict[str, str],
                              profile: Profile = SINGLE_FILE) -> str:
    """single-file profile 的规范节。

    `profile` 必须是**解析过配置行之后**的那份（`_apply_config` 的产物）——
    生成节里的行数上限、必需清单、交付用词都得跟审计实际执行的规则一致。
    拿模块常量 `SINGLE_FILE` 生成，区文档写了 `max_lines`/`entry`/`java_checks`
    就会产出「生成节说 150 行、审计按 260 行放行」这种自相矛盾的文档。

    缺省参数保留原常量，单独调用（旧外部脚本）行为不变。
    """
    out: list[str] = _section_head(area_name, profile, mapping)
    out.extend(_mapping_block(mapping))
    out.extend(_required_tables(profile, mapping))

    allowed_java = sorted(_allowed_java_names(mapping, profile))
    entry = _entry_name(mapping, profile) or "<入口>"
    # 入口可能已含在 allowed_java 里（Java 约定下 `<Xxx>Experiment.java` 就是其中之一），
    # 去重后再列，免得写成「只允许出现入口 X 与 X、Screenshot.java」。
    allowed_impl = sorted(set(allowed_java) | {entry} - {None})
    out.append("**代码实现必须单文件**（硬性）")
    out.append("")
    out.append(
        "整个版本目录里（含任何子目录）只允许出现这 %d 个实现文件：%s"
        "。此外的实现源文件、或 `src/`、`java/` 这类源码目录，一律 FAIL。"
        % (len(allowed_impl), "、".join(f"`{n}`" for n in allowed_impl))
    )
    out.append("")
    max_lines = profile.java_max_lines
    if max_lines is None:
        out.append("**行数上限：本区已关闭**（`max_lines` = `0`）")
        out.append("")
    else:
        out.append("**每个实现源文件不得超过 %d 行**（硬性）" % max_lines)
        out.append("")
        out.append(
            "口径是**物理行**（`wc -l` 的数），**注释与空行也占额度**。"
            "注意已交付的实验一源程序是 170 行，**按此口径不达标** —— 本题的要求比实验一更严，"
            "不要以实验一的写法为长度参照。"
        )
        out.append("")
        out.append(
            "「单文件」与「≤ %d 行」是一对约束：不许拆成几个文件，也不许写长。"
            "两者共同逼出**同一文件内的组织差异**（内部类的用法、方法划分、命名、"
            "参数化与否、注释密度），而不是靠代码规模拉开区别。"
            "行数不够就精简实现，**不是把注释删掉硬凑**。"
            "`report/` 下的 Python 层与 `Screenshot.java` 不受这两条限制。"
            % max_lines
        )
        out.append("")

    out.append("**禁止**")
    out.append("")
    fixed = "、".join(
        f"`{_expand(_posix(t), mapping)}`"
        for t, req, _ in profile.spec if req and "/" not in t
    )
    # 编号动态排：`max_lines` 关掉时少一条，写死序号会跳号
    rules: list[str] = [
        f"禁止改 {fixed} 这几个名字，也禁止把入口改名。"
        "「顶层不许多放文件」指源文件与改名 —— 上表列出的产物都是许可的。"
        if fixed else
        "禁止把入口改名。「顶层不许多放文件」指源文件与改名 —— 上表列出的产物都是许可的。",
        f"禁止在这 {len(allowed_impl)} 个实现文件（{'、'.join(f'`{n}`' for n in allowed_impl)}）"
        "之外新增任何实现源文件（含子目录内），"
        "也禁止新建存放源码的目录 —— 代码实现必须单文件。",
    ]
    if max_lines is not None:
        rules.append("禁止实现源文件超过 %d 行（物理行，含注释与空行）。"
                     "超了要精简实现，不是删注释凑数。" % max_lines)
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

    # ── 提交包（由 SUBMIT_FILES 派生，勿手抄到别处）──────────────────
    # `submit` 可被配置行声明为空 —— 那时本区不生成提交包，规范节不该再画
    # 一棵空树、说「每份 0 个文件一个不能少」。按 `_submit_files` 的实际结果生成。
    files = _submit_files(profile)
    if not files:
        out.append("**区根「%s/」：本区不生成提交包**" % SUBMIT_DIR)
        out.append("")
        out.append(
            f"区文档把 `submit` 声明为空（或本 profile 不生成），所以本区**不需要** "
            f"`{SUBMIT_DIR}/`，审计也跳过这一块。交付物就留在各版版本目录里。"
        )
        out.append("")
        out.append("> 各版本的抽象方式、模块拆分、命名细节**不受本规范约束** —— 那正是风格差异的体现。")
        out.append("> 本规范只管「放在哪、叫什么」，不管「怎么写」。")
        out.append("")
        return "\n".join(out)

    out.append("**区根「%s/」：每个版本一份提交包**" % SUBMIT_DIR)
    out.append("")
    out.append(
        "各版要能以**各自独立的身份交出去**，所以每版都有自己完整的一份交付物。"
        "把交付物从「多版并存、混着开发文件」的版本目录里拎出来放 `%s/<版本名>/`，"
        "就是这个目录存在的理由 —— **包里不许混进任何开发文件**。" % SUBMIT_DIR
    )
    out.append("")
    n = len(files)
    out.append("```")
    out.append(f"{area_name}/")
    out.append(f"└── {SUBMIT_DIR}/")
    out.append("    ├── v01/")
    for i, (tmpl, _) in enumerate(files):
        branch = "└──" if i == n - 1 else "├──"
        out.append("    │   " + branch + " " + _expand(tmpl, mapping))
    # 版本数不写死：本区有几个 vNN 就画几个（`find_versions` 是通用的，
    # 生成器若写死 v01~v05，版本数不同的区会拿到一棵错的树）。
    out.append(f"    ├── v02/    ← 同上 {n} 个文件，取自 v02")
    out.append(f"    ├── v03/    ← 同上，取自 v03")
    out.append("    └── …       ← 其余各版同理，每版一个目录、各含这 "
               f"{n} 个文件，与其他版互不覆盖")
    out.append("```")
    out.append("")
    out.append(
        "**每份这 %d 个文件一个不能少、也不能多**，且 `%s/` 下的目录名必须恰好是版本名。"
        % (n, SUBMIT_DIR)
    )
    out.append("")
    for i, (tmpl, why) in enumerate(files, 1):
        out.append("%d. `%s` —— %s" % (i, _expand(tmpl, mapping), why))
    out.append("")
    # 打包入口只有在**真的允许存在**时才能出现在生成的命令里：`required` 声明后
    # 只认列出的项，没列 `_pack.py` 却让人「跑 python _pack.py」，照做就是一个
    # 「多出顶层文件」的 FAIL。判定与审计同源（`_packer_permitted`），
    # 所以生成节说的和审计判的永远一致。
    packer_ok = _packer_permitted(profile, mapping)
    if packer_ok:
        out.append(
            f"- 生成的命令：`cd <版本目录>` 然后 `python {PACKER_NAME}`。"
            f"`{PACKER_NAME}` 只从**自己所在的版本目录**取文件，不关心当前工作目录 —— "
            f"各版的 `{PACKER_NAME}` **逐字节相同**（跨版 `diff` 的锚点），"
            "在哪个版本目录里跑，就产出 `%s/<该版本名>/`。" % SUBMIT_DIR
        )
    else:
        out.append(
            f"- 生成本版 `{SUBMIT_DIR}/<版本名>/` 的那一步——本区**禁用** `{PACKER_NAME}`："
            f"它的名字不在 `required` 清单里，放进版本根会被判「多出顶层文件」。"
            f"照 `submit` 那几项把文件挑进 `{SUBMIT_DIR}/<版本名>/`；"
            f"要跑 `{PACKER_NAME}` 就把它加进 `required`。"
        )
    out.append(
        "- **`%s/` 不存在不算错**（还没打包时本就不该有），"
        "但一旦存在，每个版本目录的清单就要**严格**匹配，多一个少一个都 FAIL。"
        "缺失的版本目录会被逐个报出来。" % SUBMIT_DIR
    )
    if packer_ok:
        out.append(
            f"- `{PACKER_NAME}` 只重建**自己那一版**的子目录，不动其它版本 —— "
            "所以各版各跑一次即可，顺序无所谓，不存在互相覆盖的问题。"
        )
    if profile.readme_forbidden is not None:
        out.append(
            "- **`README.txt` 必须只描述提交包里这几个文件。** "
            + (f"它由 `{PACKER_NAME}` 逐字复制，" if packer_ok else "它会进提交包，")
            + f"而包里没有区根 `{AREA_SUMMARY}`、也没有 `report/` 与 `test/`；"
            "在 README 里列这些名字，到了提交包就成了指向不存在文件的悬空引用。"
            f"完整文件清单与「改完代码怎么重跑校验与报告」属于区根 `{AREA_SUMMARY}`。"
        )
    out.append("")
    out.append("> 各版本的抽象方式、模块拆分、命名细节**不受本规范约束** —— 那正是风格差异的体现。")
    out.append("> 本规范只管「放在哪、叫什么」，不管「怎么写」。")
    out.append("")
    out.append(
        f"> **与实验报告技能的分工**：本节的 `{SUBMIT_DIR}/` 是**版本区内**的交付包。"
        "仓库根的课程提交目录属于课程提交约定，归报告类技能管，"
        "本脚本**只查版本区内的 "
        f"`{SUBMIT_DIR}/`**，不去碰它。两处不要各写一套规则。"
    )
    out.append("")
    return "\n".join(out)


def build_snapshot_section(area_name: str, mapping: dict[str, str],
                           profile: Profile = SNAPSHOT) -> str:
    """source-snapshot profile 的规范节。

    与 `build_single_file_section` 同理：`profile` 要是配置行解析后的那份。
    """
    out: list[str] = _section_head(area_name, profile, mapping)
    out.extend(_mapping_block(mapping))

    for dead in DEAD_MAPPING_KEYS:
        if dead in mapping:
            out.append(
                "> 本区还留着 `` - `<" + dead + ">` = `" + mapping[dead] + "` `` 这一行 —— "
                "`.iml` 已不再进版本区（见下），这行映射**已无意义，删掉即可**。"
            )
            out.append("")

    out.extend(_required_tables(profile, mapping))

    out.append("**`src/` 内部不受约束**（本 profile 的要点）")
    out.append("")
    out.append(
        "快照型版本区**只锁 `src/` 这一项**：里面原有几个包、几个 `.java`、怎么分包，"
        "一律照抄原项目、审计不看。原因很简单 —— 每版是既有项目的**完整源码快照**，"
        "「实现必须单文件」在这里无意义，原项目本就是分包多文件。"
        "本 profile 因此也**不设行数上限**：裁的是「放在哪、叫什么」，不是「写多长」。"
    )
    out.append("")
    out.append("**版本区不收录 IDE 文件**（硬性）")
    out.append("")
    out.append(
        "`.iml`（IntelliJ 模块描述）、`.iws`/`.ipr`（工作区配置）、`.idea/`（IDE 缓存）"
        "**都不是版本产物**：它们是 IDE 在自己机器上的状态，每台机器都能重新生成，"
        "也不是交给老师的东西。所以版本根不要求、也不检查它们（审计直接忽略）。"
    )
    out.append("")
    out.append(
        "> 需要编译或截图时，用原项目的模块或让 IDE 自己"
        "认一下 source root 即可 —— 不必为此往 `vNN/` 里放一份 `.iml`。"
        "同理，仓库根的 IDE 文件（`.idea/`、`.iml`）也不归本技能管。"
    )
    out.append("")
    out.append("**版本根只该有 `src/`**（硬性）")
    out.append("")
    out.append(
        "版本根除 `src/` 外不放手写文档、探针、报告或 IDE 文件；"
        "对照用的文档属于区根 `" + AREA_SUMMARY + "`，编译产物与临时探针放仓库根的 `out/`。"
    )
    out.append("")

    out.append("**本 profile 不做这几类检查**（不是放宽，是前提不成立）")
    out.append("")
    out.append(
        "1. **单文件 / 行数上限**：快照本就多文件，且逐字复制自原分支 —— 无从「精简」。"
    )
    out.append(
        "2. **交付源码用词检查**：快照**不许就地改**，所以「改掉违规用词」这个动作本身被禁止。"
        "而且会误伤：「契约」在中文源码里是普通词（接口约定），不是本项目 `CONTRACT.md` "
        "的简称专属；子串检查分不出这两种用法，快照型因此一律不跑它。"
    )
    out.append(
        "3. **`README.txt` 检查**：本 profile 没有交付说明这个物件。"
    )
    out.append(
        f"4. **区根 `{SUBMIT_DIR}/` 提交包**：那是单文件型的交付物，快照型不生成。"
    )
    out.append("")
    out.append(
        "> 这几条**只在 `single-file` profile 下生效**。所以换 profile 时，"
        "审计结果会明显不同 —— 那不是「同一套规矩换了个说法」，是真的两套规矩。"
    )
    out.append("")

    out.append("**禁止**")
    out.append("")
    out.append(
        "1. 禁止改 `src/` 内的任何源码 —— 快照须与原分支逐字一致，"
        "要改写法就回源区改、重新导出，**不要在本区 `vNN/` 里直接编辑**；"
        "否则 `diff` 出来的差异会混入手工痕迹，各版对照的可信度就没了。"
    )
    out.append(
        "2. 禁止在版本根放 `src/` 之外的东西（构建产物如 `out/`、探针、手写文档、"
        "报告都不算数，审计不看你也不该提交）；"
        "IDE 元数据（`.iml`/`.iws`/`.ipr`/`.idea/`）同样**不入库、不检查**。"
    )
    out.append(
        f"3. 禁止在版本目录里放任何 md —— 文档只有区根一份 `{AREA_SUMMARY}`。"
    )
    out.append("")

    out.extend(_doc_layer_block())

    out.append("> 各版本的抽象方式、模块拆分、命名细节**不受本规范约束** —— 那正是风格差异的体现。")
    out.append("> 本规范只管「放在哪、叫什么」，不管「怎么写」。")
    out.append("")
    return "\n".join(out)


def build_section(area_name: str, mapping: dict[str, str], profile: Profile) -> str:
    """按 profile 生成区根文档里那一节规范，含首尾边界标记。

    `profile` 原样传给两个 builder —— 它必须是配置行解析后的那份，
    否则生成节会按 profile 缺省值写（如 150 行），与审计实际执行的规则对不上。
    """
    if profile.key == SNAPSHOT.key:
        body = build_snapshot_section(area_name, mapping, profile)
    else:
        body = build_single_file_section(area_name, mapping, profile)
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
    ap.add_argument("--no-submit", action="store_true",
                    help="跳过区根 提交/ 的检查（还没打过包时用）")
    args = ap.parse_args(argv)

    _setup_stdout()

    area_root: Path = args.version_area
    if not area_root.is_dir():
        print(f"× 目录不存在：{_posix(area_root)}")
        return 1

    if args.emit_spec:
        # `--only` / `--no-submit` 只对审计有意义。传了就明说被忽略，
        # 不要静默吞掉 —— 静默会让人以为那面旗子起了作用。
        dropped = [f for f, given in (("--only", args.only),
                                      ("--no-submit", args.no_submit)) if given]
        if dropped:
            print(f"⚠ {'、'.join(dropped)} 对 --emit-spec 无意义，本次忽略")
        profile, mapping, notes = _resolve_profile(area_root, args.profile)
        for n in notes:
            print(n)
        return cmd_emit(area_root, mapping, profile, args.out)

    return cmd_audit(area_root, args.only, not args.no_submit, args.profile)


if __name__ == "__main__":
    sys.exit(main())
