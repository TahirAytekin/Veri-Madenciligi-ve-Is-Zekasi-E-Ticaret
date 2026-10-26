"""İnternet demosu kontrolü (F5-12): yalnızca web/requirements.txt kurulu ortamda, DEMO=1 ile 9 sayfa hatasız açılmalı.

    pip install -r web/requirements.txt && DEMO=1 python .github/demo_kontrol.py

Panel koduna PyTorch/transformers gerektiren bir içe aktarma eklenirse demo kırılır; bu kontrol onu yakalar.
"""
import os
import sys
import time
from pathlib import Path

from streamlit.testing.v1 import AppTest

SAYFALAR = ["genel_bakis", "aksiyon_plani", "urunler", "iade_beden", "talep_stok", "finans_senaryo", "musteri_sesi",
            "asistan", "model_dogrulama"]

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    os.environ["DEMO"] = "1"
    bas = time.time()
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "web" / "app.py"), default_timeout=900)
    at.run()
    hatalar = {"açılış": [str(e.value) for e in at.exception]}
    print(f"ilk açılış ve hazırlık: {time.time() - bas:.0f} sn")
    for p in SAYFALAR:
        at.switch_page(f"sayfalar/{p}.py")
        at.run()
        hatalar[p] = [str(e.value) for e in at.exception]
        print(f"  {'✓' if not hatalar[p] else '✗'} {p}")
    kotu = {k: v for k, v in hatalar.items() if v}
    if kotu:
        for k, v in kotu.items():
            print(f"::error title=Demo {k}::{v[0][:800]}")
        sys.exit(1)
    print("✓ Demo: 9 sayfa hatasız")
