"""Web paneli için çıktıları hazırlar (F5-01): calistir.py ile aynı hat, mevcut tüm veri setleri için.

    python -m web.hazirla              # = python calistir.py --veri hepsi
"""
import sys

import calistir

if __name__ == "__main__":
    sys.argv = [sys.argv[0], "--veri", "hepsi"]
    calistir.main()
