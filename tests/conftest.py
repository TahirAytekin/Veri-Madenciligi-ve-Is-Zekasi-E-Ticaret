"""Ortak test ayarları: hazirlama/ modüllerini içe aktarılabilir yapar, ağır testleri varsayılan olarak atlar."""
import os
import sys
from pathlib import Path

import pytest

PROJE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJE / "hazirlama"))
sys.path.insert(0, str(PROJE))


def pytest_collection_modifyitems(config, items):
    if os.environ.get("AGIR_TESTLER") == "1":
        return
    atla = pytest.mark.skip(reason="ağır test; çalıştırmak için AGIR_TESTLER=1")
    for item in items:
        if "agir" in item.keywords:
            item.add_marker(atla)
