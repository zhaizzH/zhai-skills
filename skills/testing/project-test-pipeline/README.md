# project-test-pipeline

**端到端测试闭环技能**：GitHub 拉取 → 构建运行 → 测试计划 → 执行 → 测试报告 → 缺陷交接 → 提交。全程 Hermes 主会话协调。

> **范围边界**：本技能只负责**测试**（发现问题 + 证据链报告），**不包含代码修改/修复**——缺陷由用户或其他流程（claude/codex 等）处理，修复验证在下一轮测试中进行。

## 触发条件

用户说「测试完整流程」「跑一遍测试」「全流程测试」「测试闭环」。

## 核心机制

| 机制 | 说明 |
|---|---|
| 铁律：禁止猜测 | 一切结论必须有证据链（命令输出/日志/DB/代码），无法验证标「未确认」，禁止写「可能/大概」 |
| 基线文件 | `baseline-success-sha.txt` 只存全量通过无 P0 的 commit（本地维护，不入仓库），作回归对比基准 |
| 变更影响扫描 | 基线 diff → 全量回归 / 最小回归集（加速模式须标注风险范围） |
| 高风险路径超时保护 | full 导入等慢路径**纳入测试**：触发 → 验证计数增长 + 首条产出 → **最多 1 分钟**终止，不排除 |
| 数据完整性断言 | 图片 naturalWidth>0、统计=DB 全量聚合、导出行数=total |
| 3 轮止损 | 同批失败跨轮次连续 3 轮仍不过 → 阻塞，@用户决策 |

## 分层测试

Smoke Gate → L0 单元 → L2 前端构建 → L1 Agent 能力（LLM 四方核对）→ L3 接口契约 → L4 E2E 视觉（每页必截必看 / 移动视口 / 布局比例 / AI 文本核对）。

状态四态：PASS / FAIL / SKIP / LIMITED；缺陷分级 P0~P3；环境问题 LIMITED 不阻塞。

## 目录结构

```
project-test-pipeline/
├── SKILL.md                          # 主流程（8 步）
├── README.md                         # 本文件
├── references/
│   ├── at-project.md                 # AnimeTracker 项目实例（账号/服务/健康检查/外部依赖探活）
│   └── l4-visual-qa.md               # L4 视觉检查四强制规范
├── templates/
│   ├── test-plan-template.md         # 测试计划模板（含高风险路径用例/数据完整性断言）
│   └── test-report-template.md       # 测试报告模板
└── scripts/
    ├── collect-env-fingerprint.sh    # 环境指纹采集
    └── playwright-screenshot.py      # 多视口截图（桌面+移动）
```

## 使用方法

把整个目录复制到目标项目的 `.claude/skills/`（或 Hermes `~/.hermes/skills/`）下：

```bash
cp -r skills/testing/project-test-pipeline <目标项目>/.claude/skills/
```

- 跑其他项目：忽略 `references/at-project.md`（AnimeTracker 专属实例），按 SKILL.md 通用流程执行
- 测试计划/报告产出：`docs/test/plan/test-plan-<日期>.md`、`docs/test/report/test-report-<日期>.md`

---

## 快速上手

1. GitHub 拉取目标项目 → 构建运行
2. 新建测试计划（`templates/test-plan-template.md` → `docs/test/plan/test-plan-<YYYYMMDD>.md`，禁止复用旧计划）
3. 执行测试：一切结论必须证据链（命令输出/日志/DB/代码），无法验证标「未确认」
4. 产出测试报告（缺陷 + 证据），缺陷交接用户处理，不代修
5. 下一轮测试验证修复（`-r2` 新计划）

## 来源与修改记录

- **原创技能**：Hermes 测试闭环流程沉淀（非 fork）
- 范围边界：只负责测试（发现问题 + 证据链报告），不含代码修改/修复

