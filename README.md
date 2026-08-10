# zhai-skills

个人自用的 Claude Code / Claude Skills 集合仓库。按需取用，把 `skills/` 下对应的 skill 目录复制到目标项目的 `.claude/skills/` 即可直接使用。

## 目录结构

```
zhai-skills/
├── README.md                      # 本文件：集合首页
└── skills/
    ├── aivedio-cover/             # 图像生成 / 编辑 skill（GPT Image 2）
    └── aivedio-video/             # AI 新闻周报「网页视频」生成 skill
```

## Skills 一览

### [aivedio-cover](./skills/aivedio-cover/README.md)

面向 GPT Image 2 及任意 OpenAI 兼容图像接口的结构化提示词工程 + 图像生成包。一份 SKILL 定义自动适配三种运行模式，对用户无感：

| 模式 | 触发条件 | 行为 |
|---|---|---|
| A · Garden 本地出图 | `ENABLE_GARDEN_IMAGEGEN` 为真 且 有 `OPENAI_API_KEY` | 端到端：选模板 → 渲染 prompt → 调 `generate.js` / `edit.js` → 图片落盘 |
| B · 宿主原生图像工具 | Garden 关闭，宿主自带图像工具 | 渲染 prompt，交给宿主的图像工具出图 |
| C · 纯 prompt 顾问 | 无图像工具 | 退化为高质量 prompt 写手，保存 prompt 供用户粘贴到任意工具 |

内置 **18 大类、79 个结构化 prompt 模板**，覆盖海报、UI 样机、产品图、信息图、学术图、技术架构图、漫画、头像、编辑工作流等；并自动归档渲染 prompt 与生成图片（`<task-slug>-<timestamp>` 命名）。

- 文档：[中文](./skills/aivedio-cover/README.zh-CN.md) · [English](./skills/aivedio-cover/README.md)

### [aivedio-video](./skills/aivedio-video/README.md)

把每周 AI 新闻周报素材做成 **16:9「网页视频」**（点击驱动、可录屏成片），并配套句子级时间轴字幕生成工具。脚手架全套（`scaffold.sh` + `templates/` + `swiss-ikb` 主题 + `edge-tts` adapter）已 **vendored 进本 skill**，自包含、开箱即用。

- 素材（`.webfetch/*.md` / 51ai / 36kr 周报 / 资讯链接）→ 结构化 `article.md` → 口播稿 `script.md` + 7 章 `outline.md`
- Vite + React + TypeScript 生成 16:9 网页视频，每点击推进一个口播节拍
- **edge-tts** 中文口播（免费零配置），音频播完自动进片
- **句子级时间轴字幕**（srt / vtt / lrc 三份同步），剪映 / CapCut 可直接导入
- 封面 / 配图由**兄弟 skill** [aivedio-cover](./skills/aivedio-cover/README.zh-CN.md) 提供，风格锁 `references/weekly-cover-design.md`（3:4）
- 固定 swiss-ikb 主题（瑞士国际主义 · 克莱因蓝 `#002FA7`），`tsc / build / vite` 验证闭环

## 安装与使用

每个 skill 自包含。使用时把它整个目录复制到目标项目的 `.claude/skills/` 下：

```bash
# 以 aivedio-video 为例（需要它的兄弟 skill aivedio-cover 时一并复制）
cp -r skills/aivedio-video  <目标项目>/.claude/skills/
cp -r skills/aivedio-cover  <目标项目>/.claude/skills/
```

> 两个 skill 在各自 README 的示例命令里用 `<skill>` / `<g>` 指代部署位置（相对项目根 `.claude/skills/<name>`），复制后按需替换路径。

## 依赖与环境变量

| 项 | 用途 | 说明 |
|---|---|---|
| Node.js（含 npm） | aivedio-cover 脚本 / aivedio-video 脚手架 | 按项目环境 |
| bash | `scaffold.sh` / `synthesize-audio.sh` | Windows 用 Git Bash |
| jq | `synthesize-audio.sh` 读 audio-segments.json | `scoop install jq` 等 |
| edge-tts（Python） | aivedio-video 中文口播 | `pip install edge-tts` |
| mutagen（Python） | 读 mp3 真实时长做字幕时间轴 | `pip install mutagen` |
| `OPENAI_API_KEY` | aivedio-cover Mode A 出图 | 可选，按需配置 |
| `ENABLE_GARDEN_IMAGEGEN` | aivedio-cover Mode A 总开关 | 可选，按需配置 |

## License

MIT
