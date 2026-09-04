# zhai-skills

个人自用的 Claude Code / Claude Skills 集合仓库。按需取用，把 `skills/` 下对应的 skill 目录复制到目标项目的 `.claude/skills/` 即可直接使用。

当前收录 **网文创作（novel）系列** 三个技能，串成一条「扫榜选题 → 产出设定 → 逐章写作」的流水线。

## 目录结构

```
zhai-skills/
├── README.md                       # 本文件：集合首页
├── LICENSE                         # MIT 许可证
└── skills/
    └── novel/                      # 网文创作系列 skill 集合
        ├── qimao-novel-scraper/    # 七猫扫榜 → 挑标杆 → 拆前3章 → 新书设定
        ├── fanqie-novel-scraper/   # 番茄扫榜（同构于七猫版，含字体混淆反爬方案）
        └── novel-writer/           # 商业网文逐章写作 + check_novel.py 质检
            ├── SKILL.md
            ├── README.md
            ├── references/         # 规划/商业/爽感/文学/写作润色/长篇连续性/复盘铁律
            ├── scripts/check_novel.py  # 确定性质检脚本
            └── agents/openai.yaml
```

## 技能流水线

三个技能前后衔接，典型用法是：先用扫榜技能（七猫或番茄二选一）做选题决策、产出新书设定与三份材料，再交给 novel-writer 逐章落地成稿。

```
[qimao / fanqie-novel-scraper]           [novel-writer]
 扫榜 → 挑标杆 → 拆前3章 → 新书设定  ──▶  需求/角色DNA/大纲/节拍 → 逐章正文 + 质检 → 润色
        产出：新书设定 · 角色DNA · 故事大纲 · 情绪节拍表
```

## Skills 一览

### [qimao-novel-scraper](./skills/novel/qimao-novel-scraper/README.md)

七猫小说「扫榜 → 挑标杆 → 拆解前 3 章 → 生成新书设定（多候选供用户选择）」的一站式标准作业程序。Step 0 需求采集 + Step 1–8 全流程，产物落盘 `小说扫榜/<书名>/{正文,材料}/`。依赖 playwright MCP 浏览器工具（curl 亦可，七猫无反爬）。核心原则：换皮不换骨——保留标杆的爽感骨架，但世界观/身份/金手指/人物关系全部换掉，确保不构成抄袭。

- 触发词：「扫七猫」「七猫扫榜」「看看七猫新书」「挑一本标杆书」「对标写新书」
- 源自 [Yunshiro/yunn-skills](https://github.com/Yunshiro/yunn-skills)（MIT），本仓库增强版（新增 Step 0 需求采集、落盘约定细化、踩坑补录）。

### [fanqie-novel-scraper](./skills/novel/fanqie-novel-scraper/README.md)

番茄小说扫榜（同构于 qimao）：`/rank` 榜单 → `/page` 详情 → `/reader` 章节。番茄为 SSR 渲染，榜单/详情/章节链接可 curl 直抓；但**正文有字体混淆反爬**（书名 100%、正文约 12% 高频字为私有区乱码），采用「渲染截图 + 视觉模型读图」还原，实测还原度 100%。流程与落盘约定同七猫版。

- 触发词：「扫番茄」「番茄扫榜」「看看番茄新书」「对标番茄写新书」
- 本仓库自建（2026-08-12 实测），结构参照 qimao 版，番茄 URL/选择器/反爬方案非原仓库内容。

### [novel-writer](./skills/novel/novel-writer/README.md)

商业网文（七猫/番茄/起点风格）逐章写作技能。把创作拆成可确认、可恢复、可验证的**六阶段工作流**（需求采集 → 角色 DNA → 故事大纲 → 情绪节拍 → 正文创作 → 分层润色），配套 `scripts/check_novel.py` 确定性质检脚本、长篇幅跨会话连续性，以及开新书的双书复盘避坑铁律。按平台约束章节标题字数（番茄 ≤30、七猫 ≤20）。配合扫榜技能产出的设定/材料使用。

- 触发词：「写小说」「写第 N 章」「续写小说」「质检章节」「修复章节质检」
- 源自 [Yunshiro/yunn-skills](https://github.com/Yunshiro/yunn-skills)（MIT），本仓库增强版（`check_novel.py` 支持 `--exclude-words`、感知词表修正；references 增补长批量实测经验）。

## 安装与使用

每个 skill 自包含。使用时把它整个目录复制到目标项目的 `.claude/skills/` 下：

```bash
# 网文流水线：扫榜技能按平台二选一，再配合 novel-writer 写作
cp -r skills/novel/qimao-novel-scraper  <目标项目>/.claude/skills/
cp -r skills/novel/fanqie-novel-scraper <目标项目>/.claude/skills/
cp -r skills/novel/novel-writer         <目标项目>/.claude/skills/
```

> novel-writer 的质检脚本以 `<skill-dir>/scripts/check_novel.py` 调用（`<skill-dir>` 为部署后的 skill 目录），不要把脚本重新写进提示词或项目目录。

## 依赖与环境

| 项 | 用途 | 说明 |
|---|---|---|
| playwright MCP（浏览器工具） | 七猫/番茄扫榜、渲染页面取 DOM/截图 | 榜单 tab 为 JS 切换时需浏览器渲染 |
| curl | 番茄/七猫 SSR 直抓详情与章节链接 | 番茄正文乱码，仍需视觉还原 |
| 视觉模型（读图 OCR） | 番茄正文字体混淆反爬还原 | 截图后读图，实测 100% |
| Python 3.10+ | novel-writer 的 `check_novel.py` 质检与标准库回归测试 | 仅用标准库，无需额外依赖 |

## License

MIT
