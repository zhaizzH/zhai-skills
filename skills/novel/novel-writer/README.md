# novel-writer

商业网文（七猫/番茄/起点风格）逐章写作技能：章法约束 + 质检脚本（check_novel.py）+ 长篇幅连续性。

## 触发词

「写小说」「写第N章」「续写小说」「质检章节」「修复章节质检」

## 快速上手

1. 配合扫榜技能（qimao-novel-scraper / fanqie-novel-scraper）产出的新书设定/角色DNA/故事大纲/情绪节拍表使用
2. 每章 prompt 强制：读上一章 + 节拍表 + 角色DNA → 2500 字±200 → 固定主角 POV → ≥3 身体感官 → 去 AI 味 → 每章一爽一钩 → 落盘后跑质检
3. 质检脚本：`scripts/check_novel.py chapter --target 2500 --hero <主角名> <章节文件>`
4. 支持批量写作（逐章写作→质检→自动修复→通知）、审校、文风修复（模板句扫描）

## 来源与修改记录

- **原作者仓库**：[Yunshiro/yunn-skills](https://github.com/Yunshiro/yunn-skills)（MIT License）
- **本仓库增强**（相对原版）：
  - `scripts/check_novel.py` 硬化：支持 `--exclude-words`（角色名含「三」如钱三金避免误爆三字阈值）、感知词表修正（后颈不算/后脖算）
  - references/planning.md、long-form-continuity.md、writing-and-revision.md 增补长批量实测经验（节拍表全卷前置、句法模板滥用检查、完结收尾清单）
