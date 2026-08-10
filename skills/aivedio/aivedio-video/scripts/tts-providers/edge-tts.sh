# edge-tts provider — free, uses Microsoft Edge's TTS backend, no API key.
# Install: pip install edge-tts
# Voices:  edge-tts --list-voices  (zh-CN-XiaoxiaoNeural 女声 / zh-CN-YunxiNeural 男声)

tts_check() {
  command -v edge-tts >/dev/null || { echo "✗ edge-tts not found" >&2; return 1; }
}

tts_install_help() {
  cat <<'EOF' >&2
Install edge-tts (free, uses Microsoft Edge's TTS backend, no API key):
  pip install edge-tts
List available voices:
  edge-tts --list-voices | less
EOF
}

tts_synthesize() {
  local text="$1" out="$2" voice="${3:-zh-CN-XiaoxiaoNeural}"
  # --file avoids shell-escaping issues with multi-line Chinese text;
  # --rate=+20% matches the project's narration pace convention.
  local tmp="$out.txt"
  printf '%s' "$text" > "$tmp"
  edge-tts --file "$tmp" --voice "$voice" --rate=+20% --write-media "$out" >/dev/null 2>&1
  local code=$?
  rm -f "$tmp"
  return $code
}
