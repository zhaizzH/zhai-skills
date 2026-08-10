# aivedio-video

把每周 AI 新闻周报素材做成 **16:9 "网页视频"**（点击驱动、可录屏成片），并配套**句子级时间轴字幕**生成工具。

本 skill 源自 AiVedio 项目反复沉淀的周报视频生成习惯。脚手架全套 —— `scripts/scaffold.sh` + `templates/` + `themes/swiss-ikb/` + `scripts/tts-providers/edge-tts.sh` —— 已 **vendored 进本 skill**，自包含、开箱即用，**无需再安装 base skill `web-video-presentation`**。

---

## 它能做什么

- 把周报素材（`.webfetch/*.md` / 51ai / 36kr 周报 / 用户丢来的资讯链接）整理成结构化 `article.md`
- 一次产出**口播稿 script.md + 7 章制 outline.md**（每章信息池必带来源标注）
- 用 Vite + React + TypeScript 生成 16:9 网页视频：每点击推进一个口播节拍，每一步独占整屏
- 合成 **edge-tts** 中文口播（免费、零配置、中文音色好），音频播完自动进片
- 生成**句子级时间轴字幕**（srt/vtt/lrc 三份同步），每句一条带起止时间的 cue，剪映 / CapCut 可直接导入
- 生成**视频封面 / 配图**（兄弟 skill aivedio-cover，位于 `.claude/skills/aivedio-cover/`；3:4 封面风格锁 `references/weekly-cover-design.md`）
- tsc / build / vite 验证闭环

## 何时触发 / 何时不用

**触发**：用户说"做这周的 AI 新闻视频 / 新一期 weekly 周报 / 周报网页视频 / 把周报素材做成网页视频 / 用项目习惯、老规矩、套路做 / 用 swiss-ikb 克莱因蓝那套做 / 这期 weekly 开始做"；或给出 `.webfetch/` 素材、本周 AI 资讯链接；或要"加字幕 / 生成字幕 / 出 srt/vtt/lrc / 按句子级时间轴"；或要"做封面 / 出缩略图 / 生成视频封面 / 加张配图"。

**不用它**：素材是普通口播稿/文章（非 AI 新闻周报），或用户明确要别的主题风格 —— 退回通用流程 `/web-video-presentation`。

## 快速开始

```bash
# 1. 脚手架（目标用相对路径；swiss-ikb 主题天然锁定，无需 --theme）
bash <skill>/scripts/scaffold.sh ./presentation
cd presentation

# 2. 开发章节：替换 src/chapters/01-example/，在 src/registry/chapters.ts 注册
#    每章必有 narrations.ts（数组长度 = step 数 = 口播唯一真相源）
#    useStepper 的 STORAGE_KEY 改成 presentation-cursor-weekly-<N>-v<X>

# 3. 口播音频（默认 edge-tts，scaffold 已接线）
npm run extract-narrations
npm run synthesize-audio          # 换男声：PRESENTATION_TTS_VOICE=zh-CN-YunxiNeural

# 4. 句子级字幕
python <skill>/scripts/gen-subtitles.py --project .   # 输出 public/subtitles.{srt,vtt,lrc}

# 5. 验证 + 录屏
npx tsc -p tsconfig.app.json --noEmit && npm run build
npx vite                          # 打开后 URL 加 ?auto=1 全自动录屏
```

## 工作流概览

| Phase | 内容 |
|---|---|
| 0 | 素材抓取 → 结构化 `article.md`（主题分节、每条新闻带来源 URL） |
| 1 | 一次产出 `script.md`（`---` 分节拍，全角标点）+ `outline.md`（7 章制，信息池带来源），然后**与用户一次对齐** |
| 2 | `bash <skill>/scripts/scaffold.sh ./presentation` + 章节开发（第 1 章强制主线程实现 + 用户验收，后续可按 A 逐章 / B 顺序 / C 并行 ≤3） |
| 3 | `npm run extract-narrations` + `npm run synthesize-audio`（默认 edge-tts）；`python scripts/gen-subtitles.py` 出字幕 |
| 4 | `npx tsc` + `npm run build` + `npx vite` 实测 golden path |

详细执行细则（脚本规约、信息池格式、checkpoint 对齐、反模式清单）见 [`SKILL.md`](./SKILL.md)。

## 依赖

| 依赖 | 用途 | 安装 |
|---|---|---|
| Node.js（含 npm） | Vite / React / TS 脚手架与构建 | 按项目环境 |
| bash | 跑 `scaffold.sh` / `synthesize-audio.sh`（Windows 用 Git Bash） | 按项目环境 |
| jq | `synthesize-audio.sh` 读 audio-segments.json | `brew install jq` / `apt-get install jq` / `scoop install jq` |
| edge-tts（Python） | 中文口播合成 | `pip install edge-tts` |
| mutagen（Python） | 读 mp3 真实时长做字幕时间轴 | `pip install mutagen` |

脚手架、templates、swiss-ikb 主题、edge-tts adapter 已随本 skill vendored，无需安装任何 base skill。

## 目录结构

```
skills/aivedio-video/
├── SKILL.md                          # Claude 读取的指令（触发 + 完整工作流 + 反模式）
├── README.md                         # 本文件（人类可读说明）
├── references/
│   ├── weekly-design-spec.md         # swiss-ikb 设计圣经（token / 字号 / 动效 / 章节 CSS 约定）
│   └── weekly-cover-design.md        # 视频封面设计规范（3:4）
├── scripts/
│   ├── scaffold.sh                   # ★ 脚手架（vendored + 适配：锁定 swiss-ikb / 默认 edge-tts）
│   ├── gen-subtitles.py              # 句子级字幕生成（srt/vtt/lrc），路径自动推导
│   └── tts-providers/
│       └── edge-tts.sh               # edge-tts 口播合成 adapter（scaffold 自动拷进项目）
├── templates/                        # ★ 脚手架模板（vendored：App / useStepper / 组件 / 样式 / 音频管线）
├── themes/
│   └── swiss-ikb/                    # ★ 唯一主题（tokens.css + theme.json），锁定
└── ../aivedio-cover/                   # ★ 兄弟 skill：图像生成（封面 / 配图），独立可调用
    ├── SKILL.md                      # aivedio-cover 主文件（A/B/C 三模式 + 18 大类模板索引）
    ├── scripts/                      # check-mode / generate / edit（node）
    └── references/                   # 80+ 结构化 prompt 模板
```

## 附带工具

### `scripts/scaffold.sh`

一键脚手架：`npm create vite` + 用本 skill 的 `templates/` 与 `themes/swiss-ikb/` 生成 16:9 网页视频项目（App / useStepper / Stage / ProgressBar / AutoToggle / 音频管线），并把 `synthesize-audio` 的 npm script 默认设为 edge-tts，跑完自动 typecheck。weekly 主题锁定 swiss-ikb，传其他 `--theme` 会报错。

```bash
bash <skill>/scripts/scaffold.sh --list-themes   # 列出可用主题（只有 swiss-ikb）
bash <skill>/scripts/scaffold.sh ./presentation  # 目标用相对路径
```

### `scripts/gen-subtitles.py`

按**句子级时间轴**生成字幕：先按空行切段落、再按 `。！？` 切句，每句独立一条带起止时间的 cue。时间轴对齐运行时真实播放（每 step 用 mutagen 读 mp3 真实时长，段间加 0.2s 间隔 = 运行时 `trailMs: 200`）。

```bash
# 项目内跑（根 = 脚本上级目录）
python scripts/gen-subtitles.py

# 从 skill 目录调用，指向某个 presentation
python <skill>/scripts/gen-subtitles.py --project <presentation-dir>
```

输出 `public/subtitles.srt` + `.vtt` + `.lrc`（UTF-8，三份同步更新）。

### `scripts/tts-providers/edge-tts.sh`

edge-tts provider adapter（实现 `tts_synthesize` / `tts_check` / `tts_install_help` 契约）。scaffold 自动拷进 presentation 的 `scripts/tts-providers/` 并接线为默认 provider，无需手动操作。默认音色 `zh-CN-XiaoxiaoNeural`（晓晓·女声），合成速度 `--rate=+20%`，用 `--file` 传文本防 shell 转义。

### `aivedio-cover/`（兄弟 skill：封面 / 配图生成）

视频封面 / 配图生成能力由**兄弟 skill** 提供，位于 `.claude/skills/aivedio-cover/` —— 自带 SKILL.md、脚本与 80+ 结构化 prompt 模板，**独立可调用**，内部含 weekly 集成节（锁定本 skill 的 `references/weekly-cover-design.md`）。封面风格权威源 `references/weekly-cover-design.md`（3:4，纯色净暖白底 + 克莱因蓝几何元素，无照片 / 渐变 / 阴影 / 圆角 / emoji）。命令里 `<g>` = `.claude/skills/aivedio-cover`（相对项目根）。

```bash
# 1. 定模式（A=Garden 本地出图 / B=交宿主图像工具 / C=纯 prompt 顾问）
node <g>/scripts/check-mode.js

# 2. Mode A 直接出封面（把 weekly-cover-design.md 模板渲染后的 prompt 填进来）
node <g>/scripts/generate.js \
  --prompt "…封面模板渲染后的 prompt…" --size 1080x1440 \
  --image weekly/weekly-<N>/cover.png \
  --prompt-output weekly/weekly-<N>/cover-prompt.md
```

## 设计约定（swiss-ikb）

- 主题固定 **swiss-ikb**（瑞士国际主义 · 克莱因蓝 `#002FA7`），**不可切换变体**
- 净暖白画布 + 极细发丝网格 + 直角 + 无渐变无阴影
- 大数字 200 Extra-Light（越大越细），1080p 必须放大字号
- 完整 token / 字号 / 动效 / 章节 CSS 前缀规则见 [`references/weekly-design-spec.md`](./references/weekly-design-spec.md)

## 素材目录约定

原始周报素材统一存 `.webfetch/`（正文约定），由抓取工具（firecrawl / WebFetch / curl）生成。
