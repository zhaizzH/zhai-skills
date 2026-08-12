#!/usr/bin/env bash
# 环境指纹采集 — 供测试报告「1. 基础信息」使用。
# 用法: bash collect-env-fingerprint.sh
# 输出为报告可复制的文本块；缺项如实标注「未安装/不可达」，禁止编造。
set -u

echo "=== 时间 ==="
date '+%Y-%m-%d %H:%M:%S %Z'

echo "=== OS ==="
uname -a
grep -E '^(NAME|VERSION)=' /etc/os-release 2>/dev/null || echo "(无 /etc/os-release)"

echo "=== 资源 ==="
free -h | sed -n '1,2p'
swapon --show 2>/dev/null || echo "(无 swap)"
echo "CPU 核数: $(nproc)"

echo "=== 工具链 ==="
java -version 2>&1 | head -1 || echo "java: 未安装"
mvn -version 2>/dev/null | head -1 || echo "mvn: 未安装"
node -v 2>/dev/null || echo "node: 未安装"
npm -v 2>/dev/null || echo "npm: 未安装"
python3 --version 2>/dev/null || echo "python3: 未安装"

echo "=== Docker 容器与镜像 ==="
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}' 2>/dev/null || echo "docker: 不可用"

echo "=== 关键中间件探活 ==="
redis-cli ping 2>/dev/null || echo "redis: 不可达"
# 按项目扩展，例：
# mysql -h127.0.0.1 -P3306 -utest -ptest -e 'SELECT VERSION();' 2>/dev/null || echo "mysql: 不可达"
# curl -sf http://localhost:9090/-/healthy && echo "minio: ok" || echo "minio: 不可达"

echo "=== 应用服务探活（按项目实例补端点） ==="
# 后端: curl -sf <真实接口> && echo "backend: ok" || echo "backend: 不可达"
# 前端: curl -sf -o /dev/null -w '%{http_code}' <页面 URL>
