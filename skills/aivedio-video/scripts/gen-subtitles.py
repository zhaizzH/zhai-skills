#!/usr/bin/env python3
"""
gen-subtitles.py — generate subtitle files aligned to the presentation
timeline (weekly 系列, sentence-level 时间轴).

Rule (per skill/aivedio-video/SKILL.md §Phase 3):
  • Every narration segment = one audio step. Auto-mode plays each mp3
    then waits `trailMs` (200ms) before advancing, so the timeline is:
        segment_start += mp3_duration + GAP_S
  • Each segment's text is split paragraph-first (blank line), then by
    sentence-ending punctuation `。！？` — every sentence gets its own cue
    with its own start/end time (never merged into one block).
  • A segment's mp3 duration is distributed across its sentences
    proportional to character count.

Reads audio-segments.json (produced by `npm run extract-narrations`),
measures real mp3 durations with mutagen (falls back to len×0.25s), and
writes public/subtitles.srt + public/subtitles.vtt + public/subtitles.lrc
(UTF-8). Paths are derived from the project root, so the same script works
for every weekly-N/presentation.

Usage:
    # From inside a project's scripts/ (root = parent dir):
    python scripts/gen-subtitles.py
    # Bundled copy invoked from anywhere, pointing at a project:
    python <skill>/scripts/gen-subtitles.py --project <presentation-dir>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from mutagen.mp3 import MP3

SCRIPT_DIR = Path(__file__).resolve().parent

# Auto-mode wait after each audio ends (matches trailMs: 200 in src/App.tsx).
GAP_S = 0.2
# Fallback per-character seconds when an mp3 is missing/unreadable.
CHAR_FALLBACK_S = 0.25

# Paragraph separator = one or more newlines. Sentence endings = 。！？…
# Split AFTER the ending punct and keep it attached to the sentence.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？…])\s*")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate timeline-aligned subtitles (srt/vtt/lrc).")
    p.add_argument(
        "--project",
        help="presentation dir containing audio-segments.json and public/. "
             "Default: the parent of this script (project-local invocation).",
    )
    return p.parse_args()


def split_sentences(text: str) -> list[str]:
    """Paragraph-first, then sentence-level split; empty chunks dropped."""
    out: list[str] = []
    for para in re.split(r"\n+", text):
        para = para.strip()
        if not para:
            continue
        for chunk in _SENTENCE_SPLIT_RE.split(para):
            chunk = chunk.strip()
            if chunk:
                out.append(chunk)
    return out


def measure_duration(audio_path: Path, text_len: int) -> float:
    """Real mp3 duration, or char-based fallback when unavailable."""
    if audio_path.exists():
        try:
            return float(MP3(audio_path).info.length)
        except Exception as e:
            print(f"[WARN] could not read {audio_path}: {e}", file=sys.stderr)
    else:
        print(f"[WARN] missing audio: {audio_path}", file=sys.stderr)
    return max(1.0, text_len * CHAR_FALLBACK_S)


def fmt_vtt(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def fmt_srt(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h:02d}:{m:02d}:{int(s):02d},{int(round((s % 1) * 1000)):03d}"


def fmt_lrc(sec: float) -> str:
    m = int(sec // 60)
    s = sec % 60
    return f"{m:02d}:{s:05.2f}"


def main() -> int:
    args = parse_args()
    root = Path(args.project).resolve() if args.project else SCRIPT_DIR.parent
    segments_file = root / "audio-segments.json"
    audio_dir = root / "public" / "audio"
    output_dir = root / "public"

    segments = json.loads(segments_file.read_text(encoding="utf-8"))

    # Build cue list: (start, end, text) with GAP_S between segments.
    cues: list[tuple[float, float, str]] = []
    cursor = 0.0
    for seg in segments:
        text = seg["text"]
        sentences = split_sentences(text)
        if not sentences:
            continue

        audio_path = audio_dir / seg["chapter"] / f"{seg['step']}.mp3"
        duration = measure_duration(audio_path, len(text))

        weights = [len(s) for s in sentences]
        total_w = sum(weights)
        start = cursor
        for sent, w in zip(sentences, weights):
            span = duration * w / total_w if total_w else duration / len(sentences)
            cues.append((start, start + span, sent))
            start += span
        cursor = start + GAP_S

    # VTT
    vtt = ["WEBVTT", "Kind: captions", "Language: zh-CN", ""]
    for start, end, text in cues:
        vtt.append(f"{fmt_vtt(start)} --> {fmt_vtt(end)}")
        vtt.append(text)
        vtt.append("")
    (output_dir / "subtitles.vtt").write_text(
        "\n".join(vtt), encoding="utf-8"
    )

    # SRT
    srt: list[str] = []
    for i, (start, end, text) in enumerate(cues, 1):
        srt.append(str(i))
        srt.append(f"{fmt_srt(start)} --> {fmt_srt(end)}")
        srt.append(text)
        srt.append("")
    (output_dir / "subtitles.srt").write_text(
        "\n".join(srt), encoding="utf-8"
    )

    # LRC
    lrc = [f"[{fmt_lrc(start)}]{text}" for start, _end, text in cues]
    (output_dir / "subtitles.lrc").write_text(
        "\n".join(lrc) + "\n", encoding="utf-8"
    )

    total = cursor - GAP_S if cues else 0.0
    print(f"[OK] {len(cues)} cues -> subtitles.vtt / subtitles.srt / subtitles.lrc")
    print(f"     total timeline: {fmt_srt(total)}")

    by_chapter: dict[str, float] = {}
    idx = 0
    for seg in segments:
        n = len(split_sentences(seg["text"]))
        times = cues[idx : idx + n]
        idx += n
        dur = sum(e - s for s, e, _ in times)
        by_chapter[seg["chapter"]] = by_chapter.get(seg["chapter"], 0.0) + dur
    for ch, dur in by_chapter.items():
        print(f"  {ch}: {dur:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
