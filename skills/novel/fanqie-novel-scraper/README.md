# fanqie-novel-scraper

番茄小说扫榜 → 挑标杆 → 拆解前 3 章 → 生成新书设定（多候选供用户选择）的一站式技能。与 qimao-novel-scraper 同构，平台换成番茄。

## 触发词

「扫番茄」「番茄扫榜」「看看番茄新书」「挑一本番茄标杆书」「对标番茄写新书」

## 快速上手

1. 番茄为 SSR 渲染，curl 可直抓榜单/详情/章节链接；**正文有字体混淆反爬**（书名 100%、正文 ~12% 高频字为私有区乱码）→ 用「渲染截图 + 视觉模型读图」还原（实测还原度 100%）
2. 结构速查：榜单 `/rank`（男/女频新书榜/阅读榜/衍生榜 tab）、详情 `/page/{bookid}`、章节 `/reader/{chapterid}`（详情页 HTML 直接含全部章节链接）
3. 流程与落盘约定同 qimao-novel-scraper（Step 0-8 + `小说扫榜/<书名>/{正文,材料}/`）

## 来源与修改记录

- **结构参照**：[qimao-novel-scraper](https://github.com/Yunshiro/yunn-skills)（Yunshiro/yunn-skills，MIT License）——同构改造
- **本仓库自建**：番茄 URL 结构、选择器、字体混淆反爬应对（截图+视觉 OCR）均为 2026-08-12 实测
- 本技能为新增技能，非 Yunshiro 原仓库内容
