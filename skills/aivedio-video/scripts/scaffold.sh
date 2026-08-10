#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# scaffold.sh —— 一键脚手架，创建一个 weekly 网页视频项目。
#
# weekly 系列固定 swiss-ikb 主题，本 skill 只 vendored 这一个主题，
# 因此无需（也无法）换主题 —— 锁定由单一主题目录天然保证。
#
# 用法：
#   bash scripts/scaffold.sh <target-dir>
#   bash scripts/scaffold.sh --list-themes
#
# 例子：
#   bash <path-to-aivedio-video>/scripts/scaffold.sh ./presentation
#
# 跑完后，章节写法见本 skill SKILL.md "swiss-ikb 设计规范" +
# references/weekly-design-spec.md（权威源）。
# ─────────────────────────────────────────────────────────────
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATES="$SKILL_DIR/templates"
THEMES_DIR="$SKILL_DIR/themes"
DEFAULT_THEME="swiss-ikb"   # weekly 系列锁定，不可换

list_themes() {
  echo "可用主题（来自 ${THEMES_DIR}）:"
  echo
  for dir in "$THEMES_DIR"/*/; do
    [[ -d "$dir" ]] || continue
    local meta="$dir/theme.json"
    [[ -f "$meta" ]] || continue
    # 没有 jq，简单 grep + sed 提字段
    local id name desc
    id=$(grep -E '"id"' "$meta" | head -n1 | sed -E 's/.*"id":[[:space:]]*"([^"]+)".*/\1/')
    name=$(grep -E '"nameZh"' "$meta" | head -n1 | sed -E 's/.*"nameZh":[[:space:]]*"([^"]+)".*/\1/')
    desc=$(grep -E '"descriptionZh"' "$meta" | head -n1 | sed -E 's/.*"descriptionZh":[[:space:]]*"([^"]+)".*/\1/')
    printf "  • %-18s %s\n      %s\n\n" "$id" "$name" "$desc"
  done
  echo "weekly 系列固定 ${DEFAULT_THEME}，--theme 传其他值会报错。"
}

# ── 解析参数 ──
TARGET=""
THEME="$DEFAULT_THEME"
for arg in "$@"; do
  case "$arg" in
    --list-themes)
      list_themes
      exit 0
      ;;
    --theme=*)
      THEME="${arg#--theme=}"
      ;;
    --*)
      echo "✗ 未知参数: $arg" >&2
      exit 1
      ;;
    *)
      if [[ -z "$TARGET" ]]; then TARGET="$arg"; fi
      ;;
  esac
done

TARGET="${TARGET:-presentation}"
THEME_DIR="$THEMES_DIR/$THEME"
THEME_TOKENS="$THEME_DIR/tokens.css"

if [[ ! -d "$THEME_DIR" || ! -f "$THEME_TOKENS" ]]; then
  echo "✗ 找不到主题 '${THEME}'。weekly 固定 ${DEFAULT_THEME}，只有这一个主题。" >&2
  exit 1
fi

if [[ -d "$TARGET" && -n "$(ls -A "$TARGET" 2>/dev/null || true)" ]]; then
  echo "✗ 目标目录 '${TARGET}' 已存在且非空，已中止。" >&2
  exit 1
fi

if ! command -v npm >/dev/null; then
  echo "✗ 需要 npm，但在 PATH 里没找到。" >&2
  exit 1
fi

echo "▸ 在 $TARGET 创建 Vite + React + TS 项目"
echo "▸ 使用主题：$THEME（weekly 固定）"
npm create vite@latest "$TARGET" -- --template react-ts >/dev/null

cd "$TARGET"
echo "▸ 安装依赖（可能要等一会）..."
npm install >/dev/null 2>&1

echo "▸ 安装 tsx（用于 extract-narrations 脚本）..."
npm install --save-dev tsx >/dev/null 2>&1

echo "▸ 用演示骨架替换默认 boilerplate"

# 干掉我们不要的 Vite 默认 boilerplate
rm -f \
  src/App.tsx src/App.css \
  src/main.tsx src/index.css \
  src/assets/react.svg \
  public/vite.svg \
  README.md
rmdir src/assets 2>/dev/null || true

# 把脚手架文件拷到项目根
mkdir -p \
  src/styles src/hooks src/components src/registry \
  src/chapters/01-example \
  public scripts

cp "$TEMPLATES/vite.config.ts" .
cp "$TEMPLATES/index.html" .

cp "$TEMPLATES/src/main.tsx" src/main.tsx
cp "$TEMPLATES/src/App.tsx"  src/App.tsx

# tokens.css 来自 swiss-ikb 主题（唯一 vendored 主题）
cp "$THEME_TOKENS"                          src/styles/tokens.css
cp "$TEMPLATES/src/styles/base.css"         src/styles/base.css
cp "$TEMPLATES/src/styles/animations.css"   src/styles/animations.css
cp "$TEMPLATES/src/styles/fonts.css"        src/styles/fonts.css

cp "$TEMPLATES/src/hooks/useStageScale.ts"   src/hooks/useStageScale.ts
cp "$TEMPLATES/src/hooks/useStepper.ts"      src/hooks/useStepper.ts
cp "$TEMPLATES/src/hooks/useAudioPlayer.ts"  src/hooks/useAudioPlayer.ts
cp "$TEMPLATES/src/hooks/useAutoMode.ts"     src/hooks/useAutoMode.ts

cp "$TEMPLATES/src/components/Stage.tsx"          src/components/Stage.tsx
cp "$TEMPLATES/src/components/MaskReveal.tsx"     src/components/MaskReveal.tsx
cp "$TEMPLATES/src/components/ProgressBar.tsx"    src/components/ProgressBar.tsx
cp "$TEMPLATES/src/components/ProgressBar.css"    src/components/ProgressBar.css
cp "$TEMPLATES/src/components/AutoStartGate.tsx"  src/components/AutoStartGate.tsx
cp "$TEMPLATES/src/components/AutoStartGate.css"  src/components/AutoStartGate.css
cp "$TEMPLATES/src/components/AutoToggle.tsx"     src/components/AutoToggle.tsx
cp "$TEMPLATES/src/components/AutoToggle.css"     src/components/AutoToggle.css

cp "$TEMPLATES/src/registry/types.ts"    src/registry/types.ts
cp "$TEMPLATES/src/registry/chapters.ts" src/registry/chapters.ts

cp "$TEMPLATES/src/chapters/01-example/Example.tsx"     src/chapters/01-example/Example.tsx
cp "$TEMPLATES/src/chapters/01-example/Example.css"     src/chapters/01-example/Example.css
cp "$TEMPLATES/src/chapters/01-example/narrations.ts"   src/chapters/01-example/narrations.ts

# Audio pipeline scripts (extract-narrations + synthesize-audio runner).
cp "$TEMPLATES/scripts/extract-narrations.ts"  scripts/extract-narrations.ts
cp "$TEMPLATES/scripts/synthesize-audio.sh"    scripts/synthesize-audio.sh
chmod +x scripts/synthesize-audio.sh

# weekly 只用 edge-tts 这一个 provider，adapter 已在 skill 里 vendored
mkdir -p scripts/tts-providers
cp "$SKILL_DIR/scripts/tts-providers/edge-tts.sh" scripts/tts-providers/edge-tts.sh

# Wire the audio scripts into npm. edge-tts 是 weekly 默认 provider，
# 直接内嵌到 npm script，跑 `npm run synthesize-audio` 即可。
node -e '
const fs = require("fs");
const p = JSON.parse(fs.readFileSync("package.json", "utf8"));
p.scripts = Object.assign({}, p.scripts, {
  "extract-narrations": "tsx scripts/extract-narrations.ts",
  "synthesize-audio":   "PRESENTATION_TTS=edge-tts bash scripts/synthesize-audio.sh",
});
fs.writeFileSync("package.json", JSON.stringify(p, null, 2) + "\n");
'

# 留个标记，以后能查这个项目从哪个主题起步的
{
  echo "$THEME"
} > .theme

# 跑一次 typecheck 确认接线 OK
echo "▸ 跑 typecheck ..."
if npx tsc --noEmit; then
  echo "✓ typecheck 通过"
else
  echo "✗ typecheck 失败 —— 请看上面的错误" >&2
  exit 1
fi

cat <<EOF

✓ 完成。下一步：

  1. cd $TARGET
  2. npm run dev      # 默认 http://localhost:5174（被占会自动换端口）

当前主题：${THEME}（见 .theme）

然后：

  • 点舞台任意位置推进全局 step 计数器。
  • 鼠标移到底部边缘可显出进度条；鼠标移到右上角可显出播放模式切换。
  • 把 src/chapters/01-example/ 替换成你自己的章节
    （写法见本 skill SKILL.md "swiss-ikb 设计规范" + "章节技术约定" +
    反模式清单；权威源 references/weekly-design-spec.md —— 写每章前回看）。
  • 在 src/registry/chapters.ts 注册每个新章节。
  • **每章必须有 narrations.ts**（与 Example.tsx 同目录），
    数组长度 = step 数，是音频合成 + Auto 模式的唯一真相源。
  • 章节改了就 bump src/hooks/useStepper.ts 的 STORAGE_KEY 末尾版本号，
    且 key 必带周次：presentation-cursor-weekly-<N>-v<X>（防跨期游标串位）。

录制：

  • 手动模式：直接打开 http://localhost:5174（点击 / 方向键推进）
  • 半自动：URL 加 ?audio=1 — 音频跟 step 切，但你手动推进
  • 全自动录屏：URL 加 ?auto=1 — 按一次 SPACE 启动，整片自动播 + 推进
                按 M 键随时切换三种模式。

音频合成（可选，录制前做）：

  npm run extract-narrations    # 扫所有章节 narrations.ts → audio-segments.json
  npm run synthesize-audio      # 默认 edge-tts 合成 → public/audio/<id>/<step>.mp3
                                # 换音色：PRESENTATION_TTS_VOICE=zh-CN-YunxiNeural npm run synthesize-audio
                                # 需要 edge-tts：pip install edge-tts

EOF
