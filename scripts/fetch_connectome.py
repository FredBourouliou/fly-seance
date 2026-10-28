"""Download the FlyWire 630 connectome files used by Shiu et al. (2024).

The files are not redistributed in this repository. They are fetched from the
paper's code repository (MIT) at a pinned commit and checked against SHA-256.

    python scripts/fetch_connectome.py            # → data/
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

COMMIT = "91bdd1e7dcf193f3e7ca5a8933497fcef63b7960"
BASE = f"https://raw.githubusercontent.com/philshiu/Drosophila_brain_model/{COMMIT}"
FILES = {
    "2023_03_23_completeness_630_final.csv":
        "e6b71e17671a9bdb05f55e4bc6774640a1418cb7a05125e0fc994ad40f9bfdfb",
    "2023_03_23_connectivity_630_final.parquet":
        "94db8c650533bc36ffa3223f2e62325d5648b8d6bd31c3a4e1c804628c7557b3",
}
DATA = Path(__file__).resolve().parents[1] / "data"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    DATA.mkdir(exist_ok=True)
    for name, digest in FILES.items():
        target = DATA / name
        if target.exists() and sha256(target) == digest:
            print(f"ok      {name}")
            continue
        print(f"fetch   {name}")
        tmp = target.with_suffix(target.suffix + ".part")
        urllib.request.urlretrieve(f"{BASE}/{name}", tmp)
        if sha256(tmp) != digest:
            tmp.unlink()
            print(f"checksum mismatch for {name}", file=sys.stderr)
            return 1
        tmp.rename(target)
        print(f"ok      {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
