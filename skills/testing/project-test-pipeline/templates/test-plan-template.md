# 测试计划 <项目名> <YYYY-MM-DD>（第 N 轮）

> 模板说明：由 project-test-pipeline 步骤 4 使用，按 test-plan-authoring skill 标准结构产出。用例编号 `{层}-{模块}-{序号}` 发布后不可复用。旧计划只作参考，本文件须按当前 commit 与源码重新调研编写。

## §0 AI 执行者指令（交给 codex/claude 执行时必读）

- 完整六条模板见 test-plan-authoring skill 的 `references/ai-executor-instructions.md`，落盘时展开：
  1. 端点以实际代码为准（执行前 `rg "Mapping\("` 核对）
  2. 严格按层串行执行
  3. 失败二分：环境问题 → LIMITED 不阻塞；代码缺陷 → 记录+本地修复
  4. 测试账号预置，禁止中途注册（撞限流）
  5. 安全：报告不写 token/密钥
  6. 产出报告路径 + 是否自动提交以任务指令为准（默认不自动提交，留人工 review）

## 0. 元信息

- 被测分支 / commit SHA：`<sha>`（来自步骤 0 版本锚定）
- 基线 SHA（baseline-success-sha.txt）：`<sha>`；本次为 全量回归 / 最小变更驱动回归集（加速模式须标注风险范围）
- 组件清单与版本：`<组件 / 版本>`（环境指纹可用 `scripts/collect-env-fingerprint.sh` 采集）
- 执行人 / 预计时长：`<Hermes + codex> / <N 小时>`

## 1. 目标与范围

- 可验证验收标准：`<如「连续 5 次错误密码后第 6 次必须拒绝」>`
- 纳入范围 / 不纳入范围：
- 需求覆盖矩阵：需求 → 用例 ID

## 2. 环境与准入条件

- 服务清单（端口 / 启动方式 / readiness 命令）：
- 依赖清单（`docker ps` / `curl` / `redis-cli ping`）：
- **外部依赖探活（必做）**：`<curl 走实际代理路径验证外部 API/图片域名 200，命令见 references/at-project.md>`——外部依赖挂掉会制造「接口 200 但数据 0/图片 404」假象
- 数据基线：`<重置 test-seed.sql 后的基线描述>`
- Smoke Gate：所有 readiness 全过才开跑

## 3. 测试数据管理

- fixture 表：数据 | 用途 | 是否破坏性 | 清理动作
- 破坏性用例用隔离账号（如 `e2e_lock_test`）；脚本统一放 `scripts/test-fixtures/`

## 4. 用例清单

每用例必含：**ID | 优先级 | 前置条件 | 步骤 | 期望结果（可判定） | 清理 | 证据 | 状态**（执行后填）。期望结果至少含 HTTP 状态码或 UI 状态 + 一个可断言字段；接口用例必写 `code` 字段与 `data` 存在性；安全用例必写「响应不含 SQL/堆栈/token/密码」；长连接（SSE）必写 Content-Type、事件顺序、首段超时。

### 4.1 L0 单元测试（Codex 主导）— 共 N 条
- `UNIT-XXX-001` …（业务逻辑、工具类、Service 单测）

### 4.2 L1 Agent 能力（LLM 输出四方核对：LLM文本 ↔ 接口 ↔ DB ↔ 前端）— 共 N 条
- `AGENT-XXX-001` …（自然语言问句 → 聊天 SSE 接口 → 解析 answer 流 → 断言 AI 输出中的语义标签与接口数字含义一致；枚举映射缺失本身可测）

### 4.3 L2 前端构建检查 — 共 N 条
- `L2-FRONTEND-001` …（client/admin `tsc` 类型检查、`vite build` 生产构建，不依赖后端；本项目无组件单测，L2 即构建检查）

### 4.4 L3 接口契约 / 集成 — 共 N 条
- `API-XXX-001` …（OpenAPI 契约、参数校验、异常码、权限、分页；契约不匹配直接 FAIL）

### 4.5 L4 E2E + 视觉（强制项）— 共 N 条
- `E2E-XXX-001` …（登录、核心页面渲染、关键操作链路；「页面 ↔ 接口 ↔ 数据库」三方核对）
- 视觉四强制（规范见 project-test-pipeline `references/l4-visual-qa.md`）：每页必截必看（vision_analyze 看截图本身）、390×844 移动视口逐页检查、布局比例比对（gridColumn / rect 宽度，不只看溢出）、AI 助手生成文本四方核对。移动端专项放最后，报 `mobile-layout` 通过率。
- **数据完整性断言（强制）**：页面 img `naturalWidth>0`（图片加载检查）；统计卡片数值 == DB 全量聚合；导出行数 == total
- **可读性断言（前端可读性改动必做，防回归）**：`L4-READ-001` WCAG 对比度检查——`--text-soft`/`colorTextSecondary` ≥4.5:1（浅色）/≥4.0:1（深色），`--text-faint`/`colorTextTertiary` ≥4.5:1（浅色）/≥4.0:1（深色）。取 getComputedStyle 实际色值 + 相对亮度公式计算。实测基准：admin 浅色 soft #4c5c6a=6.13、faint #5c6c7a=4.81（#6b7c8b=3.82 未达标已加深）；深色 soft #b7c6d0=9.93、faint #8496a2=5.68

### 4.6 高风险路径用例（超时保护，不排除）
- `HIGH-XXX-001` full/慢导入：触发 → 验证**扫描阶段计数增长（subject_count > 0）** + 首条数据产出 → **最多 1 分钟超时**终止并记录（不等待完整跑完）；报告标注「部分验证：仅扫描+首条产出，未全量」
- `HIGH-XXX-002` 其他长任务：同类超时保护模式

### 4.6 Flaky 用例清单（独立统计，标记 FLAKY，不占用 3 轮止损配额）
- `<ID> | 触发条件 | 重试策略`（持续维护于 docs/test/flaky-cases.md）

## 5. 执行顺序与缺陷流程

- 严格按层串行：Smoke Gate → L0 → L2 → L1 → L3 → L4
- 状态四态：PASS / FAIL / SKIP / LIMITED；叠加缺陷分级 P0~P3；环境问题标 LIMITED 不阻塞，代码缺陷标 FAIL
- 缺陷流程：记录（ID/层/证据链/复现步骤）→ **交接用户修复**（本技能不含代码修改；修复验证在下一轮测试受影响用例覆盖）→ 同批失败连续 3 轮（跨轮次）仍不过 → 停止 @用户决策

## 6. 风险与退出标准

- 风险表：环境 / 数据 / 外部依赖 / 长连接
- **长任务保护**：full/慢导入等用例**最多 1 分钟超时**（验证计数增长+首条产出即终止），禁止等待完整跑完；终止时记录 id 并标 FAILED
- 退出标准：无未处置 P0、P1 有结论
- 阻断标准：核心依赖不可用且 30 分钟无法恢复 → 停该层，报告构建/环境错误

## 7. 报告模板

执行完成后按 `templates/test-report-template.md` 产出 `docs/test/report/test-report-<YYYYMMDD>.md`（同日多轮 `-r2` 后缀）。
