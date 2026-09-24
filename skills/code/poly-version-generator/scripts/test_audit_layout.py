#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`audit_layout.py` 的判据自检 —— 不依赖真实版本区：

    python poly-version-generator/scripts/test_audit_layout.py

只覆盖一处**真实踩过的假阳性**：二进制资源被当源码做用词检查。
`src/img/bg2.jpg` 里有一串字节碰巧凑出 `v30`，于是每个含该图的版本都被判
「源码里不许带版本号」。用词检查只对文本有意义，故必须跳过二进制。

退出码 0 = 全通过；1 = 断言失败。
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_layout as A      # noqa: E402

def _mk_area(root: Path) -> Path:
    """造一个最小的 source-snapshot 版本区：area/v01/src/..."""
    area = root / "Demo" / "poly-demo"
    (area / "v01" / "src").mkdir(parents=True)
    (area / "v01" / "src" / "Main.java").write_text(
        "public class Main { public static void main(String[] a){} }\n", encoding="utf-8")
    return area

def main() -> int:
    d = Path(tempfile.mkdtemp())
    try:
        area = _mk_area(d)

        # 文本源码：能解码。用词检查要扫到它。
        (area / "v01" / "src" / "Main.java").write_text(
            "public class Main { /* v30 */ }\n", encoding="utf-8")
        files = {str(p) for p in A._source_files(area / "v01", A.PROFILES["source-snapshot"])}
        assert any(f.endswith("Main.java") for f in files), files

        # 二进制资源：不能当文本读，必须被筛掉 —— 否则字节凑出的「v30」造成假阳性。
        jpg = area / "v01" / "src" / "bg2.jpg"
        jpg.write_bytes(bytes(range(256)) * 4 + b"v30")
        assert not A._is_text_file(jpg), "二进制文件不该判为文本"
        files = {str(p) for p in A._source_files(area / "v01", A.PROFILES["source-snapshot"])}
        assert not any(f.endswith("bg2.jpg") for f in files), files

        # src/ 不存在的版本：由 4.2 报缺目录，_source_files 只需平静返回空。
        (area / "v02").mkdir()
        assert A._source_files(area / "v02", A.PROFILES["source-snapshot"]) == []
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("SELF-CHECK OK")
    return 0

if __name__ == "__main__":
    sys.exit(main())
