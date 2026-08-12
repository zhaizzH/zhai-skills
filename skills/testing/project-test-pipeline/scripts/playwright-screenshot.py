#!/usr/bin/env python3
"""多视口页面截图 — 供 Hermes L4 视觉检查与缺陷存证。

用法:
  python3 playwright-screenshot.py <输出目录> <视口宽:高>... <URL>...
示例:
  python3 playwright-screenshot.py /tmp/l4-shots 1280:800 390:844 \
      http://localhost:3000/ http://localhost:3000/subject/1

可选登录（页面需登录时）:
  --login-url <URL> --login-user <u> --login-pass <p>
  --login-user-selector <css> --login-pass-selector <css> --login-submit-selector <css>
  默认选择器: input[type=text],input[type=password],button[type=submit]（可覆盖）

依赖: pip install playwright && playwright install chromium
实测坑（来自 project-test-pipeline references/l4-visual-qa.md）:
  - 页面有轮询/SSE 时 networkidle 永不触发 → 统一 domcontentloaded + 固定等待
  - 截图是主动视觉检查手段，截完必须 vision_analyze 看截图本身
"""
import argparse
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("缺少 playwright: pip install playwright && playwright install chromium")


def sanitize(url: str) -> str:
    return url.replace("://", "_").replace("/", "_").replace("?", "_").replace("&", "_")[:60]


def main() -> int:
    ap = argparse.ArgumentParser(description="多视口页面截图")
    ap.add_argument("outdir", help="截图输出目录")
    ap.add_argument("viewports", nargs="+", help="视口列表，如 1280:800 768:900 390:844")
    ap.add_argument("urls", nargs="+", help="要截图的 URL 列表")
    ap.add_argument("--wait-ms", type=int, default=1500, help="domcontentloaded 后的固定等待（毫秒）")
    ap.add_argument("--full-page", action="store_true", help="整页截图（默认仅首屏）")
    ap.add_argument("--login-url")
    ap.add_argument("--login-user")
    ap.add_argument("--login-pass")
    ap.add_argument("--login-user-selector", default="input[type=text], input[type=email]")
    ap.add_argument("--login-pass-selector", default="input[type=password]")
    ap.add_argument("--login-submit-selector", default="button[type=submit]")
    args = ap.parse_args()

    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    viewports = [tuple(int(v) for v in vp.split(":")) for vp in args.viewports]

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": viewports[0][0], "height": viewports[0][1]})

        if args.login_url:
            page = context.new_page()
            page.goto(args.login_url, wait_until="domcontentloaded")
            page.wait_for_timeout(args.wait_ms)
            page.fill(args.login_user_selector, args.login_user)
            page.fill(args.login_pass_selector, args.login_pass)
            page.click(args.login_submit_selector)
            page.wait_for_timeout(args.wait_ms)
            page.close()

        for vw, vh in viewports:
            for url in args.urls:
                page = context.new_page()
                page.set_viewport_size({"width": vw, "height": vh})
                try:
                    page.goto(url, wait_until="domcontentloaded")
                    page.wait_for_timeout(args.wait_ms)
                    name = f"{vw}x{vh}_{sanitize(url)}.png"
                    page.screenshot(path=str(out / name), full_page=args.full_page)
                    print(f"OK  {out / name}")
                except Exception as e:  # noqa: BLE001
                    print(f"ERR {vw}x{vh} {url}: {e}", file=sys.stderr)
                finally:
                    page.close()

        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
