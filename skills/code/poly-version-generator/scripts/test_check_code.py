#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`check_code.py` 的静态检查自检 —— 不依赖 JDK，直接跑：

    python poly-version-generator/scripts/test_check_code.py

覆盖四类判据的边界（这些是「误报/漏报」最容易出问题的地方）：
  · 不同包同名 Main → 合法，不报
  · 同包同名（文件名与类名不一致，如 `Dup.java` 里写 `class Main`）→ 必报
  · `import java.util.*` / `foo.*` → 不算未解析；`import nope.Missing` → 报
  · 能解析到本树兄弟文件的 import → 不报
  · 编译/运行契约正文含三条硬约束关键字
退出码 0 = 全通过；1 = 有断言失败（脚本有问题，不是被测代码有问题）。
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_code as C          # noqa: E402


def main() -> int:
    d = Path(tempfile.mkdtemp())

    def w(rel: str, txt: str) -> None:
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt, encoding="utf-8")

    try:
        # 不同包同名类：合法。报它就是误报，会逼人给本来没冲突的代码改名。
        w("v01/src/a/Main.java", "package a;\npublic class Main {}\n")
        w("v01/src/b/Main.java", "package b;\npublic class Main {}\n")
        assert C.check_static(d / "v01") == [], C.check_static(d / "v01")

        # 同包同名类：必报。判据是「包 + 类名」，故文件名不同于类名也要抓到。
        w("v02/src/p/Main.java", "package p;\npublic class Main {}\n")
        w("v02/src/p/Dup.java", "package p;\npublic class Main {}\n")
        probs = C.check_static(d / "v02")
        assert any("类名冲突" in x and "p.Main" in x for x in probs), probs

        # import：JDK 前缀与通配不算本树文件；外部包名报出来。
        w("v03/src/q/Main.java",
          "package q;\nimport java.util.List;\nimport foo.*;\n"
          "import nope.Missing;\npublic class Main {}\n")
        probs = C.check_static(d / "v03")
        assert len(probs) == 1 and "nope.Missing" in probs[0], probs

        # 解析得到的本树 import：不报。
        w("v04/src/r/Main.java", "package r;\nimport r.Helper;\npublic class Main {}\n")
        w("v04/src/r/Helper.java", "package r;\nclass Helper {}\n")
        assert C.check_static(d / "v04") == [], C.check_static(d / "v04")

        # 契约正文必须含三条硬约束的判据关键字，否则规则会被悄悄写丢。
        text = C.build_run_contract("poly-x")
        for key in ("-implicit:none", "$(find src -name '*.java')", "check_code.py"):
            assert key in text, key
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("SELF-CHECK OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
