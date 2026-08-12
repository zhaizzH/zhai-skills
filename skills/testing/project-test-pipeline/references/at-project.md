# AnimeTracker 项目实例细节

本文件是 project-test-pipeline 的 AnimeTracker（番组手账）项目专属实例。主流程见 SKILL.md；跑其他项目时本文件不适用。

## 环境与身份

- 路径：`/home/zhaizz/projects/AnimeTracker`，属主 zhaizz（uid 1000）。
- git：root 操作前 `git config --global --add safe.directory <path>`；身份操作 `sudo -u zhaizz git pull`；root 拉取后 `chown -R zhaizz:zhaizz <proj>`。
- 测试环境：本机运行，**local profile**。
- 测试账号：client `test1/123456`、admin `admin/123456`（预置，禁止中途注册撞限流）。

## 服务与资源

- 守护服务：`animetracker-agent.service`、`animetracker-business.service`。systemd 会在 kill 后自动拉起进程 → **测前 stop，测后 enable + start**；测试过程中如发现服务被偷偷拉起，先查 `systemctl status` 与 journal。
- 同机其他项目：测前顺带停 nginx、kb-rag 释放内存（物理机 3.8G RAM，必要时扩 swap：`fallocate -l 8G /swapfile && mkswap && swapon && 写 /etc/fstab`）。
- 健康检查（无 actuator）：后端 `POST /api/client/auth/login` 返回 `code=200`；前端页面 HTTP 200。
- 响应包装：`Result<T>{code, message, data}`。
- 防爆破解锁：测完 `redis-cli -n 1 del auth:login-fail:<user>`（Redis 用 db 1）。

## 文档与数据

- 接口文档：`docs/spec/openapi.yaml`；DB 文档：`docs/database/db-schema.sql`；种子数据：`docs/test/test-seed.sql`（版本化，每次重置重放）。
- 数据一致性核对例：页面番剧总数 ↔ `GET /api/admin/dashboard` ↔ `SELECT COUNT(*) FROM subject`，三者必须一致。
- 执行方式（最新实测，2026-08-11 起）：**hermes 主会话直接执行**，L4 浏览器实测 + 截图检查为强制项；L0 大批量用例可派 codex 读 `docs/test/plan/` 下本次新建的计划执行。

## 外部依赖探活（Smoke Gate 必做）

- Bangumi API：`curl -s -m 10 -x http://127.0.0.1:7890 -o /dev/null -w '%{http_code}' "https://api.bgm.tv/v0/subjects?type=2&year=2026&month=7&offset=0&limit=1"` → 期望 200（走本机 mihomo 代理；直连被墙）
- 封面图片域名：`curl -s -m 10 -x http://127.0.0.1:7890 -o /dev/null -w '%{http_code}' "https://lain.bgm.tv/pic/cover/l/28/9d/234_hIMht.jpg"` → 期望 200
- MinIO 数据可达性：subject.image 字段 URL `curl --noproxy '*'` 抽查（192.168.0.3:9000 局域网直连）
- 代理配置基线：mihomo 127.0.0.1:7890（规则含 bgm.tv/lain.bgm.tv 走节点）；agent `.env`：BANGUMI_BASE_URL=https://api.bgm.tv + HTTPS_PROXY=http://127.0.0.1:7890 + NO_PROXY=localhost,127.0.0.1 + MINIO_ENDPOINT=192.168.0.3:9000

## 高风险路径测试规则

- full 导入：纳入测试但**最多 1 分钟超时**——触发 → 验证 subject_count 增长（扫描阶段计数已修复，每 3 秒刷新）+ 首条数据产出 → 终止（pkill -9 -f "importer/main.py" + DB 标 FAILED 注明），报告标注「部分验证」；禁止等待完整跑完
- 封面完整性：验证 MinIO covers 文件数增长 + 页面 img naturalWidth>0
- **L2 落地（长期定案）**：本项目前端无组件单测，L2 即 client/admin `tsc + vite build` 构建检查（构建检查是 L2 的既定内容，非过渡方案）。
- **健康检查顺序**：`POST /api/client/auth/login` 探活用 test1；必须在该账号被防爆破锁定之前执行，锁定后若需再探活，先 `redis-cli -n 1 del auth:login-fail:<user>` 解锁。

## 通知

- 需人工 review/批准/决策时 @用户：`<at user_id="ou_1480e47797ffec9e2cb4e95b279c8af8"></at>`（该 ID 也记录在 memory，若与 memory 冲突以 memory 为准）。
