#!/usr/bin/env python3
"""Deterministic chapter and manuscript checks for novel-writer.

已知踩坑（2026-08-11 实战 100 章后记录）：
- 「三字」指标 = 全文"三"字出现次数（≤8）。角色名含"三"（如钱三金）会误爆阈值——
  用 --exclude-words 列出这些词，脚本自动从其"三"字计数中扣除（如 --exclude-words 钱三金）。
- 感知词表：后脖算感知、后颈不算（词表里只有"后脖"）——审校时勿用"后颈"凑感知句，
  也不用纠正作者写"后颈"（真实身体感受，不算违规）。
- 本文件基于 Yunshiro/yunn-skills novel-writer 原版硬化（加 --exclude-words），
    其余规则与上游保持一字不差，避免与上游 diff 混乱。

本项目增强规则：
- 章节标题格式、文件章号和平台标题长度为硬性检查。
- 第一章前 800 字必须出现身体感官；其他章节不重复应用这条开篇规则。
- Windows 控制台统一使用 UTF-8 输出，避免中文网文检查在 GBK 控制台崩溃。
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PERC_PATTERN = re.compile(
    r"听见|听得|闻到|闻见|看清|觉着|觉得|心里|心口|胸口|胃里|嗓子眼|"
    r"后脖|后背|手心|眼前|鼻子里|才明白|明白过来|回过神|忽然想起|"
    r"想起|盘算|算了算|怕的是"
)
BODY_PATTERN = re.compile(
    r"饿|渴|冷|疼|酸|累|腥|馊|发软|发涩|发凉|发紧|打颤|哆嗦|"
    r"咽了口|口水|抽了一下|喘"
)
ANON_PATTERN = re.compile(
    r"有人小声|有人嘀咕|众人|旁边有人|人群里有人|不知谁|有人低声"
)
NOT_IS_PATTERN = re.compile(r"不是[^。！？\n]{1,20}[，]?是")
EVEN_PATTERN = re.compile(r"连[^。！？\n]{1,15}[都也]")
SILENCE_PATTERN = re.compile(r"没说话|沉默了|没有表情|没有回答|没吭声|不吭声")
SIMILE_PATTERN = re.compile(r"像[一二]?[个台块只场道条把]")
ENUM_PATTERN = re.compile(r"[^。！？\n]+、[^。！？\n]+、[^。！？\n]+")
TEMPLATE_PATTERN = re.compile(
    r"眼神冰冷|嘴角勾起|身躯一震|倒吸一口凉气|心中掀起|惊涛骇浪|"
    r"前所未有|一字一顿|全场死寂|落针可闻|杀意弥漫|殊不知|旋即|就在这时"
)
POSTURE_PATTERN = re.compile(r"你自己想|你会知道的|到时候你就明白|我不解释")
MARKDOWN_PATTERN = re.compile(r"^\s*(?:#{1,6}\s|[>*|+-]\s)|`|\*\*", re.MULTILINE)
NUMBER_UNIT_PATTERN = re.compile(r"[一二两三四五六七八九十百千]+(?:秒|分钟|时辰|遍|次|步|口)")
TITLE_PATTERN = re.compile(r"^# 第(?P<number>\d{2,})章·(?P<title>\S.*)$")
FILENAME_PATTERN = re.compile(r"^第(?P<number>\d{2,})章-(?P<book>.+)\.md$")
PLATFORM_TITLE_LIMITS = {"fanqie": 30, "qimao": 20}


@dataclass(frozen=True)
class Rule:
    label: str
    key: str
    op: str
    limit: float | tuple[float, float]


BASE_RULES = (
    Rule("感知句", "perception", "ge", 12),
    Rule("感知/500字", "per_500", "ge", 2),
    Rule("身体感官", "body_feeling", "ge", 3),
    Rule("无名反馈", "anonymous_feedback", "le", 0),
    Rule("破折号", "dash", "le", 5),
    Rule("三字", "three", "le", 8),
    Rule("不是A是B", "not_is", "le", 1),
    Rule("连…都/也", "even", "le", 1),
    Rule("沉默回应", "silence", "le", 3),
    Rule("比喻像…", "simile", "le", 3),
    Rule("顿号三连", "triple_enum", "le", 1),
    Rule("模板高频词", "template_phrase", "le", 0),
    Rule("装逼不解释", "posture", "le", 0),
    Rule("Markdown残留", "markdown", "le", 0),
    Rule("单句成段", "short_paragraphs", "ge", 8),
    Rule("连续单句串", "max_short_run", "le", 4),
    Rule("平均段长", "avg_paragraph", "range", (25, 35)),
    Rule("连续3段>60", "long_run", "le", 0),
    Rule("开篇3段最长", "opening_max", "le", 45),
    Rule("最长段", "longest_paragraph", "le", 60),
)


def read_body(path: Path) -> tuple[str, str, list[int]]:
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    # 只剥离首行章节标题；正文中的其他 Markdown 标记必须被检测出来。
    body = "\n".join(lines[1:]) if lines and lines[0].lstrip().startswith("#") else text
    paragraphs = [part.strip() for part in body.splitlines() if part.strip()]
    lengths = [len(re.sub(r"\s", "", part)) for part in paragraphs]
    return text, body, lengths


def resolve_title_limit(platform: str, title_limit: int | None = None) -> int:
    """Resolve the immutable platform limit or validate an explicit other-platform limit."""
    platform = platform.lower()
    if platform in PLATFORM_TITLE_LIMITS:
        if title_limit is not None:
            raise ValueError(f"{platform} 平台标题上限由规则固定，不接受 --title-limit")
        return PLATFORM_TITLE_LIMITS[platform]
    if platform != "other":
        raise ValueError("--platform 只能是 fanqie、qimao 或 other")
    if title_limit is None or title_limit <= 0:
        raise ValueError("other 平台必须提供正整数 --title-limit")
    return title_limit


def validate_title(path: Path, platform: str, title_limit: int | None = None) -> tuple[list[str], int | None]:
    """Validate the canonical title and filename contract; return failures and chapter number."""
    text = path.read_text(encoding="utf-8-sig")
    first_line = text.splitlines()[0].strip() if text.splitlines() else ""
    title_match = TITLE_PATTERN.fullmatch(first_line)
    filename_match = FILENAME_PATTERN.fullmatch(path.name)
    failures: list[str] = []
    title_number: int | None = None
    file_number: int | None = None

    if not title_match:
        failures.append("章节标题格式必须为：# 第01章·标题")
    else:
        title_number = int(title_match.group("number"))
        title_text = title_match.group("title")
        try:
            limit = resolve_title_limit(platform, title_limit)
        except ValueError as error:
            failures.append(str(error))
        else:
            visible_length = len(re.sub(r"\s", "", title_text))
            if visible_length > limit:
                failures.append(f"章节标题字数={visible_length}，要求 ≤{limit}")

    if not filename_match:
        failures.append("章节文件名必须为：第01章-书名.md")
    else:
        file_number = int(filename_match.group("number"))
        if title_number is not None and file_number != title_number:
            failures.append(f"文件章号={file_number} 与标题章号={title_number} 不一致")

    if first_line.count("#") == 0:
        failures.append("缺少章节标题")
    extra_headings = re.findall(r"^\s*#{1,6}\s", "\n".join(text.splitlines()[1:]), re.MULTILINE)
    if extra_headings:
        failures.append("正文包含额外 Markdown 标题")
    # 文件名参与稿件排序，优先用它决定“第一章”规则；标题错误时仍不能绕过首章检查。
    chapter_number = file_number if file_number is not None else title_number
    return failures, chapter_number


def longest_short_run(lengths: Iterable[int]) -> int:
    current = 0
    longest = 0
    for length in lengths:
        current = current + 1 if length <= 15 else 0
        longest = max(longest, current)
    return longest


def inspect(path: Path, hero: str = "", exclude_words: tuple[str, ...] = ()) -> dict[str, object]:
    text, body, lengths = read_body(path)
    compact = re.sub(r"\s", "", body)
    word_count = len(compact)
    perception = len(PERC_PATTERN.findall(body))
    number_units = NUMBER_UNIT_PATTERN.findall(body)
    repeated_units = sorted({item for item in number_units if number_units.count(item) > 1})
    hero_pattern = re.compile(re.escape(hero) + r"[^。！？\n]{0,12}(?:" + PERC_PATTERN.pattern + r")") if hero else None
    sanitized = body
    for word in sorted(set(word.strip() for word in exclude_words if word.strip()), key=len, reverse=True):
        sanitized = sanitized.replace(word, "")
    three_count = sanitized.count("三")

    return {
        "file": path.name,
        "word_count": word_count,
        "perception": perception,
        "hero_perception": len(hero_pattern.findall(body)) if hero_pattern else None,
        "per_500": round(perception / max(word_count / 500, 1), 1),
        "body_feeling": len(BODY_PATTERN.findall(body)),
        "anonymous_feedback": len(ANON_PATTERN.findall(body)),
        "dash": body.count("——"),
        "three": three_count,
        "not_is": len(NOT_IS_PATTERN.findall(body)),
        "even": len(EVEN_PATTERN.findall(body)),
        "silence": len(SILENCE_PATTERN.findall(body)),
        "simile": len(SIMILE_PATTERN.findall(body)),
        "triple_enum": len(ENUM_PATTERN.findall(body)),
        "template_phrase": len(TEMPLATE_PATTERN.findall(body)),
        "posture": len(POSTURE_PATTERN.findall(body)),
        "markdown": len(MARKDOWN_PATTERN.findall(body)),
        "short_paragraphs": sum(length <= 15 for length in lengths),
        "max_short_run": longest_short_run(lengths),
        "avg_paragraph": round(sum(lengths) / len(lengths), 1) if lengths else 0,
        "long_run": sum(
            1 for index in range(len(lengths) - 2)
            if all(length > 60 for length in lengths[index:index + 3])
        ),
        "opening_max": max(lengths[:3]) if lengths else 0,
        "longest_paragraph": max(lengths) if lengths else 0,
        "repeated_units": repeated_units,
        "opening_800_has_body": bool(BODY_PATTERN.search(compact[:800])),
    }


def rule_passes(value: float, rule: Rule) -> bool:
    if rule.op == "le":
        return value <= float(rule.limit)
    if rule.op == "ge":
        return value >= float(rule.limit)
    low, high = rule.limit  # type: ignore[misc]
    return low <= value <= high


def limit_text(rule: Rule) -> str:
    if rule.op == "le":
        return f"≤{rule.limit}"
    if rule.op == "ge":
        return f"≥{rule.limit}"
    low, high = rule.limit  # type: ignore[misc]
    return f"{low}~{high}"


def evaluate(
    metrics: dict[str, object],
    target: int | None,
    title_failures: Iterable[str] = (),
    chapter_number: int | None = None,
) -> list[str]:
    failures: list[str] = []
    failures.extend(title_failures)
    if target is not None:
        count = int(metrics["word_count"])
        if not target - 200 <= count <= target + 200:
            failures.append(f"字数={count}，要求 {target - 200}~{target + 200}")

    for rule in BASE_RULES:
        value = float(metrics[rule.key])
        if not rule_passes(value, rule):
            failures.append(f"{rule.label}={metrics[rule.key]}，要求 {limit_text(rule)}")

    repeated = metrics["repeated_units"]
    if repeated:
        failures.append(f"重复时间量词={repeated}")
    if chapter_number == 1 and not metrics["opening_800_has_body"]:
        failures.append("第一章前800字缺少身体感官")
    return failures


def print_chapter(
    path: Path,
    metrics: dict[str, object],
    target: int | None,
    platform: str,
    title_limit: int | None = None,
) -> bool:
    title_failures, chapter_number = validate_title(path, platform, title_limit)
    failures = evaluate(metrics, target, title_failures, chapter_number)
    print(f"\n{path.name}")
    if target is not None:
        ok = target - 200 <= int(metrics["word_count"]) <= target + 200
        print(f"  {'字数(含标点)':<14} {metrics['word_count']!s:<8} [{target - 200}~{target + 200}] {'✓' if ok else '✗'}")
    for rule in BASE_RULES:
        value = metrics[rule.key]
        print(f"  {rule.label:<14} {value!s:<8} [{limit_text(rule)}] {'✓' if rule_passes(float(value), rule) else '✗'}")
    if metrics["hero_perception"] is not None:
        print(f"  {'主角名附近感知':<14} {metrics['hero_perception']}")
    print(f"  {'重复时间量词':<14} {metrics['repeated_units'] or '无'}")
    if chapter_number == 1:
        print(f"  {'第一章前800字身体感':<14} {'有 ✓' if metrics['opening_800_has_body'] else '无 ✗'}")
    else:
        print(f"  {'第一章前800字身体感':<14} 不适用")
    print("  人工检查：开篇500字人名≤3、地名≤1，且不要求读者现场计算。")
    if failures:
        print("  结论：未通过")
        for failure in failures:
            print(f"    - {failure}")
        return False
    print("  结论：机械指标通过；仍须按 Skill 要求人工通读。")
    return True


def natural_key(path: Path) -> list[tuple[int, object]]:
    return [
        (0, int(part)) if part.isdigit() else (1, part)
        for part in re.split(r"(\d+)", path.name)
    ]


def chapter_files(directory: Path) -> list[Path]:
    return sorted((path for path in directory.glob("*.md") if path.is_file()), key=natural_key)


def split_exclude(args: argparse.Namespace) -> tuple[str, ...]:
    return tuple(dict.fromkeys(w.strip() for w in args.exclude_words.split(",") if w.strip()))


def configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, OSError):
                pass


def run_chapter(args: argparse.Namespace) -> int:
    path = args.file.resolve()
    if not path.is_file():
        print(f"错误：章节文件不存在：{path}", file=sys.stderr)
        return 2
    return 0 if print_chapter(
        path,
        inspect(path, args.hero, split_exclude(args)),
        args.target,
        args.platform,
        args.title_limit,
    ) else 1


def run_manuscript(args: argparse.Namespace) -> int:
    directory = args.directory.resolve()
    if not directory.is_dir():
        print(f"错误：章节目录不存在：{directory}", file=sys.stderr)
        return 2
    files = chapter_files(directory)
    if not files:
        print(f"错误：目录中没有 Markdown 章节：{directory}", file=sys.stderr)
        return 2

    failed: list[tuple[str, list[str]]] = []
    print(f"{'章节':<24}{'字数':>7}{'感知':>7}{'密度':>7}{'身体':>7}{'无名':>7}{'破折号':>8}{'三':>5}{'沉默':>6}{'短段':>6}")
    for path in files:
        metrics = inspect(path, args.hero, split_exclude(args))
        title_failures, chapter_number = validate_title(path, args.platform, args.title_limit)
        failures = evaluate(metrics, args.target, title_failures, chapter_number)
        print(
            f"{path.stem:<24}{metrics['word_count']:>7}{metrics['perception']:>7}"
            f"{metrics['per_500']:>7}{metrics['body_feeling']:>7}"
            f"{metrics['anonymous_feedback']:>7}{metrics['dash']:>8}"
            f"{metrics['three']:>5}{metrics['silence']:>6}{metrics['short_paragraphs']:>6}"
        )
        if failures:
            failed.append((path.name, failures))

    if failed:
        print(f"\n未通过：{len(failed)}/{len(files)} 章")
        for name, failures in failed:
            print(f"  {name}")
            for failure in failures:
                print(f"    - {failure}")
        return 1
    print(f"\n机械指标通过：{len(files)}/{len(files)} 章；仍须按 Skill 要求人工通读。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="检查小说章节的代入感、排版和常见 AI 痕迹指标。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    chapter = subparsers.add_parser("chapter", help="检查一个章节文件")
    chapter.add_argument("file", type=Path)
    chapter.add_argument("--target", type=int, required=True, help="目标字数，允许上下浮动 200 字")
    chapter.add_argument("--platform", choices=("fanqie", "qimao", "other"), required=True, help="发布平台；决定章节标题字数上限")
    chapter.add_argument("--title-limit", type=int, help="other 平台的章节标题字数上限")
    chapter.add_argument("--hero", default="", help="主角姓名，用于附加感知统计")
    chapter.add_argument("--exclude-words", default="", help="逗号分隔的角色名等专有名词，从其\"三\"字计数中扣除（如 钱三金）")
    chapter.set_defaults(func=run_chapter)

    manuscript = subparsers.add_parser("manuscript", help="检查目录中的全部 Markdown 章节")
    manuscript.add_argument("directory", type=Path)
    manuscript.add_argument("--target", type=int, help="统一目标字数；各章目标不同时省略")
    manuscript.add_argument("--platform", choices=("fanqie", "qimao", "other"), required=True, help="发布平台；决定章节标题字数上限")
    manuscript.add_argument("--title-limit", type=int, help="other 平台的章节标题字数上限")
    manuscript.add_argument("--hero", default="", help="主角姓名，用于附加统计")
    manuscript.add_argument("--exclude-words", default="", help="逗号分隔的角色名等专有名词，从其\"三\"字计数中扣除（如 钱三金）")
    manuscript.set_defaults(func=run_manuscript)
    return parser


def main() -> int:
    configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args()
    try:
        resolve_title_limit(args.platform, args.title_limit)
    except ValueError as error:
        parser.error(str(error))
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
