---
name: project-test-pipeline
description: "Use when 用户要求跑测试完整流程。GitHub拉取到commit的端到端测试闭环。"
version: 1.6.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [testing, pipeline, regression, ci]
    related_skills: [test-plan-authoring]
---

# Project Test Pipeline（端到端测试闭环）

用户（zhaizz）定义的完整测试工作流：GitHub 拉取 → 构建运行 → 测试计划 → 执行 → 测试报告 → 缺陷交接 → 提交。hermes 主会话全程协调。

> **范围边界**：本技能只负责**测试**（发现问题 + 证据链报告），**不包含代码修改/修复**——缺陷由用户或其他流程（claude/codex 等）处理，修复验证在下一轮测试中进行。

- 项目实例细节（路径/账号/服务名/健康检查等）见 **references/at-project.md**（本项目 AnimeTracker）。
- L4 视觉检查详细规范见 **references/l4-visual-qa.md**（步骤 4/5 执行 L4 前必读）。
- 资产：计划/报告模板见 **templates/**；环境指纹采集 `scripts/collect-env-fingerprint.sh`、L4 多视口截图 `scripts/playwright-screenshot.py`。

## 触发条件

- 用户说「测试完整流程」「跑一遍测试」「全流程测试」「测试闭环」

## 铁律：禁止猜测（No Guessing）

测试流程中**一切结论必须有证据链**：命令输出、日志片段、DB 查询结果、代码引用、可复现步骤。证据不足时如实标注「未确认」，禁止用推断填补。违反即流程缺陷，报告作废重写。

1. **数据/计数异常**：先查时间线定位来源（DB 变更记录、应用日志、进程启动/退出时间、systemd journal、audit），用命令证明；禁止写「可能/应该是/大概率是 xxx」。
2. **触发源不明**：排查完本机全部调度器（systemd timer、crontab、hermes cron、应用内调度代码）仍无法定位 → 结论固定写「触发源未定位（已排除：xxx）」，建议用户提供线索或加日志观测；禁止猜测「可能是用户手动点击」。
3. **FAIL 根因未确认**：必须能复现或用日志/代码/DB 证明；做不到 → 标「未确认根因」，进受限/待查清单，不写推测性根因。
4. **报告措辞**：PASS/FAIL 判定与根因描述禁止出现「可能」「也许」「应该」「大概」「推测」；无法判定 → 标 UNCONFIRMED 并写明缺什么证据。
5. **观察项分级**：未经验证的观察只能进报告「待核实清单」，不能进结论性内容；待核实项后续轮次必须闭环（核实 or 移除）。

## 总体流程（8 步，0 起编号）

```
0. 版本锚定 → 1. 拉取 → 2. 构建+健康检查 → 3. 环境与数据准备
→ 4. 测试计划 → 5. 执行 → 6. 测试报告 → 7. 缺陷交接与提交
```

有 FAIL → 缺陷清单交接用户（修复由用户/外部流程处理，本技能不含代码修改）；同一批失败用例连续 3 轮（跨轮次）仍不过 → 停止，标阻塞，@用户决策。

## 详细步骤

### 0. 版本锚定（必做，防测错版本）

- 拉取前记录远端：`git ls-remote origin <branch>`，记下 HEAD SHA。
- 拉取后确认：`git log -1 --format="%H %s"`。若本地有未推送 commit，明确被测对象是「本地 HEAD」还是「远端 HEAD」，并在计划/报告中声明。
- 测试计划、测试报告、最终 commit message 全部带上这个 SHA。
- 维护基线文件 `baseline-success-sha.txt`（**本地维护，不提交仓库**，放项目根目录）：仅存储**全流程通过、无P0阻塞缺陷、无未解决受限用例**的成功commit SHA，作为回归对比基准；存在FAIL的commit禁止作为基线。
- **基线写入时机**：仅在本轮回归全绿 **且用户确认提交后**，由 Hermes 把该 commit SHA 写入基线文件。禁止提前写入（未确认的 commit 不是基线），也禁止事后补写（基线必须对应真实通过的 commit）。

### 1. 拉取代码

- **拉取前工作区卫生检查**：`git status --short` 确认工作区干净。有未提交改动 → 先向用户确认「丢弃 / 暂存 stash / 提交」，处理完再 pull；禁止带脏工作区拉取（污染 diff 对比与回归结果）。
- 用户项目在 `/home/zhaizz/projects/<proj>/`，属主 zhaizz。root 操作 git 前先 `git config --global --add safe.directory <path>`（已配过，但新项目要补）。
- 身份操作：`sudo -u zhaizz git pull`；root 拉取后要 `chown -R zhaizz:zhaizz <proj>`。

### 2. 构建并运行（含健康检查）

- 按项目文档构建（mvn / npm build 等）。
- **构建顺序（Maven 多模块）**：先 `mvn test` 拿单测结果（单测失败会中断，属正常，记 FAIL 继续），再 `mvn package -DskipTests` 出 jar；不要跳过 test 直接 package。
- **构建完成 ≠ 可用**，必须健康检查通过才算成功：后端真实接口探活（具体端点见 references/at-project.md），前端页面 HTTP 200 可访问。
- 构建或启动失败 → 停止流程，报告构建错误，不进入测试。
- 前置变更影响扫描（Hermes执行）：对比本次commit与基线SHA，`git diff <baseline-sha> HEAD --name-only`，映射文件变更范围，用于选择**全量回归 / 最小变更驱动回归集**；默认全量回归；用户明确启用加速模式时启用最小回归集，报告必须标注「非全量回归，风险范围：xxx」，不得隐瞒覆盖缺口。

### 3. 环境与数据准备

- 明确测试环境（本项目实例见 references/at-project.md：本机运行、local profile、测试账号）。
- **采集环境指纹**：跑 `scripts/collect-env-fingerprint.sh`，输出存报告「基础信息」（报告必须带环境指纹，出现偶现 bug 才能精确复现）。
- **测试前停守护服务**（有 systemd 守护时 kill 进程会自动重启；测完恢复）。顺带停同机其他项目释放内存。
- **清环境变量污染**：`unset CORS_ORIGINS` 或 `env -u CORS_ORIGINS` 启动——shell 里的 `CORS_ORIGINS=*` 会让 pydantic 解析 list 失败，agent 起不来、**pytest collection 全挂**（14 个文件全 ERROR 的实测案例）。任何 python 服务/测试前先确认该变量。
- **内存不足时扩 swap**：`fallocate -l 8G /swapfile && mkswap && swapon && 写 /etc/fstab`（物理机 3.8G RAM 实测必需）。
- 依赖确认：`docker ps`、`redis-cli ping`、`curl` 各服务。
- **版本化种子数据重置**：禁止依赖手工预置账号/字典数据；每次重置执行 `docs/test/test-seed.sql`（仓库内，随项目提交），重置至统一干净基线；禁止直接使用生产快照做E2E测试，如需真实样本必须脱敏。
- **数据契约前置校验**：核对 DB 实际表结构与 `docs/database/db-schema.sql` 一致性（字段、类型、索引、NOT NULL、外键）；校验DTO ↔ OpenAPI ↔ DB字段、枚举映射一致性。
- 重置脏测试数据；记录数据基线。
- Smoke Gate：所有 readiness 全过才开跑测试。
- **外部依赖探活（Smoke Gate 必做）**：测试前探活外部数据源/代理连通性（如 Bangumi API、封面图片域名）——用 curl 走实际代理路径验证 200。外部依赖挂掉会制造「接口 200 但数据 0/图片 404」的假象（实测案例：第三方代理挂掉导致 full 导入 0 条、封面全部 404，测试前不探活就无法区分环境故障与产品缺陷）。具体命令见 references/at-project.md。
- 防爆破测试会锁账号：测完按项目实例解锁（注意 Redis 用的 db 号）。

### 4. 编写测试计划（每次必写新计划）

- **每次测试必须新建测试计划**：按 `templates/test-plan-template.md` 产出 `docs/test/plan/test-plan-<YYYYMMDD>.md`，同日多轮加 `-r2` 后缀（如 test-plan-2026-08-10-r2.md）。**禁止直接复用旧计划文件**——旧计划只作参考（历史用例、已知缺陷、环境信息），须按当前 commit 与源码重新调研编写。`-r2` 语义：同日多轮的**新**计划（重新调研），不是旧计划的延续。
- **分层定义与准入阻断规则固化**
  - L0：单元测试，业务逻辑、工具类、Service单测；前置执行，大面积失败（阈值可配置，默认>10%）可阻断进入高层测试，快速失败
  - L1：Agent业务能力层，LLM自然问答、收藏状态映射等AI逻辑；强制四方核对：LLM输出文本 ↔ 接口 ↔ DB ↔ 前端展示；脚本自动核对字符串易误报，以人工通读原文为准（实测案例：replace bug 误报「看过」，人工核对确认 PASS）
  - L2：前端构建检查（tsc 类型检查 + vite build，验证编译与生产构建通过，不依赖后端服务）；**本项目长期以构建检查作为 L2 内容**（无组件单测，见 references/at-project.md）；若项目引入 React 组件单测（渲染、props 校验），并入本层
  - L3：接口契约/集成测试，OpenAPI契约、参数校验、异常码、权限、分页；契约不匹配直接标记FAIL，不推迟到L4才发现
  - L4：E2E+视觉浏览器实测（**强制项**，不可跳过、不可仅用接口测试替代）
- **缺陷分级规则（计划、报告强制携带）**
  - P0阻断：核心链路崩溃、登录失败、数据错乱、写入脏数据；必须修复，不允许放行
  - P1严重：功能可用但核心场景异常、移动端不可操作、AI语义映射错误；优先修复，可协商临时降级开关
  - P2一般：次要布局瑕疵、非关键交互、文案错误；不阻塞上线，登记技术债排期修复
  - P3低优：微调视觉、非关键提示、文档问题；直接进入backlog，不阻塞本次交付
- **Flaky不稳定用例管理**：维护独立清单 `docs/test/flaky-cases.md`，记录间歇性失败用例、触发条件、重试策略；flaky用例标记`FLAKY`，不占用常规3轮修复止损循环；连续多轮随机失败转入专项根因排查，禁止用无限重试掩盖bug；flaky占比超阈值（默认>5%）增加上线风险提示；首次运行无该文件时按表头 `用例ID | 触发条件 | 重试策略 | 状态` 初始化。
- **L4 视觉检查四强制**：每页必截必看（vision_analyze 看截图本身）、移动端 390×844 视口、布局比例检查（不只看溢出）、AI 助手生成文本四方核对。详细规范与实测案例见 **references/l4-visual-qa.md**。
- **数据完整性断言（强制项，防"接口 200 但数据缺失"盲区）**：
  - 图片/封面：页面 img 元素 `naturalWidth > 0` 或 fetch 图片 URL 200；DB 的 URL 字段抽查可达性（实测教训：image 指向不可达 IP/被墙域名，页面布局正常但图全裂，测试只查布局不查图片）
  - 统计卡片：数值必须等于全量聚合（DB 对照），不接受"统计窗口/本页"等局部口径——除非需求明确如此并在报告标注
  - 导出类：导出行数 == 列表 total（全量）
- **高风险路径不排除（防范围盲区）**：full 导入等被标记"风险高/慢"的路径必须纳入测试——用**超时保护**而非排除：触发后验证「扫描阶段计数增长 + 首条数据产出」，**最多 1 分钟超时**后终止并记录，不等待完整跑完。实测教训：full 被"禁止"排除后，代理挂掉导致 full 0 条持续一周未被发现。
- 加载 **test-plan-authoring** skill，按其六原则/四态/编号规范产出 AI 可执行计划。
- **先读 docs 目录**：浏览项目 `docs/` 全部内容——接口文档、数据库文档、约定文档、历史测试计划/报告，全部作为用例来源与预期依据。
- **写前必做代码调研**：rg 核对真实 controller 端点（接口文档可能与代码漂移）、响应包装结构（如 `Result<T>{code,message,data}`）、DTO 字段、测试文件数。不沿用旧文档，不编造。
- 计划放 `docs/test/plan/test-plan-<YYYYMMDD>.md`，顶部含 AI 执行者指令（§0）。
- 可选扩展层（默认不启用，用户显式指令才执行）
  - L5 混沌测试：网络抖动、Redis/DB 断开、超时、并发锁
  - L5 性能基准：接口P95、吞吐量，对比基线评估性能退化
  - L5 轻量SAST扫描：依赖漏洞、硬编码密钥、不安全注解

### 5. 执行测试计划

- 严格按层串行：Smoke Gate → L0单元 → L2前端构建 → L1Agent能力 → L3接口 → L4 E2E视觉。
- 状态四态：PASS / FAIL / SKIP / LIMITED；叠加缺陷分级P0~P3；不稳定用例标记`FLAKY`独立统计，不与普通FAIL混排。环境问题标 LIMITED 不阻塞；代码缺陷标 FAIL。
- **L4 截图用 `scripts/playwright-screenshot.py`**（多视口批量截图，自动处理 domcontentloaded 等待），截完必用 `vision_analyze` 看截图本身（详细规范见 references/l4-visual-qa.md）。
- 执行方式：**最新实测（2026-08-11 起）为 hermes 主会话直接执行**，L4 浏览器实测 + 截图检查为强制项；L0 大批量用例可派 codex 读 `docs/test/plan/` 下本次新建的计划执行（见 references/at-project.md）。
- **L3 接口层执行前**：先读接口文档（`docs/spec/openapi.yaml`），按文档端点逐条冒烟；文档与代码不一致时以代码为准并在报告注明。
- **前后端联调数据一致性**（L3/L4）：前端页面展示的数据 ↔ 接口返回 ↔ 数据库实际数据三者核对一致。不一致记 FAIL 并附三方数值。
- 测试账号预置，禁止中途注册（撞限流）。

### 6. 编写测试报告

- 按 `templates/test-report-template.md` 产出报告（存 `docs/test/report/test-report-<YYYYMMDD>.md`；同一天多轮用 `-r2` 后缀），结构：
  1. 基础信息：执行环境指纹（OS、JDK/Maven/Node、Docker镜像、中间件版本、swap、profile）、被测commit SHA、基线SHA、触发人、执行起止时间
  2. 分层四态计数+通过率、耗时拆解（L0/L1/L2/L3/L4耗时）
  3. 缺陷清单：按P0/P1/P2/P3分级；失败明细（必写失败原因+日志片段，不能只写"失败"）
  4. Flaky清单、受限明细（含补测条件）、未覆盖模块风险清单
  5. 变更影响摘要、上线建议（放行 / 受限放行 / 阻塞）、回滚触发条件（上线告警阈值）
- 存 `docs/test/report/test-report-<YYYYMMDD>.md`；同一天多轮用 `-r2` 后缀。
- 审计链路：记录执行过程（进程ID、调度日志、执行起止），用于事后追溯复盘。

### 7. 缺陷交接与提交

- 有 FAIL → 整理**缺陷清单**（编号/层/根因证据链/复现步骤/日志片段）附在报告中 → **交接用户处理**（本技能不含代码修改；修复由用户或其他流程执行，修复验证在下一轮测试的受影响用例中覆盖）。
- 无 FAIL（或 FAIL 均为环境/数据问题并已定性）→ **先向用户展示测试报告总结，用户确认后再提交**：
  - 提交前把本轮结果整理成摘要发给用户：分层通过率（L0-L4 四态计数）、缺陷分级清单、产物文件路径（计划+报告）、待提交内容清单（改了哪些文件）、上线建议与回滚条件。
  - @用户请其确认「是否提交」（@格式见 references/at-project.md 或 memory），或按用户要求操作（如：不提交留人工 review、只提交部分文件、改 commit message 等）。
- 提交规范：commit message 带被测 commit SHA；用户确认后才执行提交。**注意**：`git add -A` 可能误提交本地维护文件（如 baseline-success-sha.txt）——提交前 `git status` 核对，禁止把约定不入库的文件带进 commit。
- 用户确认提交后：把该 SHA 写入 `baseline-success-sha.txt`（见步骤 0）。
- **止损**：同一批失败用例连续 3 轮（跨轮次）仍不过 → 停止，标「阻塞/需人工决策」，@用户。
- 边界约定：流水线负责预合并门禁；生产灰度冒烟属于后置补充，报告明确边界，不混淆职责；**测试通过 ≠ 自动上线，合并/上线决策权保留给用户**。

## 产物清单

- `docs/test/plan/test-plan-<YYYYMMDD>.md` — 测试计划（每次新建，按 templates/test-plan-template.md，同日多轮 `-r2`）
- `docs/test/report/test-report-<YYYYMMDD>.md` — 测试报告（按 templates/test-report-template.md，同天多轮加 `-r2` 后缀）
- `docs/test/test-seed.sql` — 版本化种子数据（随项目提交）
- `docs/test/flaky-cases.md` — 不稳定用例清单，持续维护
- `baseline-success-sha.txt` — 全流程通过基线commit（**本地维护，不提交仓库**）
- 截图存证 — `scripts/playwright-screenshot.py` 输出目录（随报告记录路径）

## Pitfalls

- 测试中臆测数据来源/触发源/FAIL原因，把猜测当结论写进报告 → 结论失真、误导修复方向；一切结论必须证据链（命令输出/日志/DB/代码/复现），无法验证的标「未确认」，见「铁律：禁止猜测」。
- 不锚定版本 → 测错版本，报告无意义；工作区脏就拉取 → diff 与回归结果被污染。
- 构建成功 ≠ 可用，必须过健康检查才开跑。
- 测试机上的报告与产物默认不提交，留人工 review（用户明确要求）。
- `git add -A` 误提交本地维护文件（baseline-success-sha.txt 等）→ 提交前 `git status` 核对（实测事故：baseline 被误 push，已修复移除）。
- DB种子脚本依赖人工预置，不同测试机数据不一致，导致"本地过、CI失败"；种子数据必须版本化、每次重置重放
- 基线SHA随便选，使用带已知bug的commit作为对比基线，回归结论失真；基线仅允许使用**全量通过无P0阻塞**的commit，且只在用户确认提交后写入
- 测试报告缺少缺陷分级，无法自动化判断上线阻断条件，所有决策依赖人工主观判断
- 环境指纹不全，出现偶现bug后无法精确复现（JDK版本、profile、swap、中间件版本差异）
- 测试排除高风险路径（如 full 导入"禁止"）→ 主功能成盲区，外部依赖故障持续存在不被发现；高风险路径用**超时保护纳入测试**（full 最多 1 分钟，验证计数增长+首条产出即终止），不排除
- 验收标准缺失 → 按"既有设计行为"断言 PASS，用户期望（统计全量/导出全量）被漏掉；计划编写时对统计/导出/列表类功能明确"范围=全量 or 局部并在报告标注"
- 断言深度不足（只查布局/状态码，不查数据完整性）→ 图片全裂/URL 不可达/统计局部化全部漏检；补：img naturalWidth、URL 可达性、统计值=DB 聚合、导出行数=total
- 外部依赖（代理/第三方 API）挂掉但被当成环境正常 → 测试前 Smoke Gate 必须探活外部依赖连通性（curl 走实际代理路径），区分环境故障与产品缺陷

## 相关 skills

- **test-plan-authoring**：步骤 4 编写标准（六原则/四态/编号/AI 执行者指令）。
- **dogfood**：探索性 QA（补充 E2E 之外的人工点检）。
