"""Verileri tek komutla günceller: Trendyol'dan çekim -> temizleme -> analiz tabloları -> panel çıktıları.

Kullanım (proje klasöründe):
  python guncelle.py                      günlük güncelleme (pazartesileri yorumlar da çekilir)
  python guncelle.py --haftalik           yorumlar dahil
  python guncelle.py --sadece finans,iadeler
  python guncelle.py --cekmeden           yalnızca temizleme + analiz (API'ye istek atmaz)
  python guncelle.py --sahte              yalnızca sahte veri analiz tabloları (API ve gerçek veri gerekmez)
  python guncelle.py --uretmeden          panel çıktılarını (calistir.py) üretme

Son adım calistir.py: kalıp, stok, yorum analizi, durum raporu, tavsiyeler, ürün kartları, asistan bilgi tabanı.
Model doğrulaması yeniden yapılmaz (docs/rapor/02_dogrulama.md dondurulmuş sonuçtur).

Her adım ayrı süreçte çalışır; biri hata verirse diğerleri devam eder, sonunda özet verilir.
Çıktı loglar/guncelle_YYYY-MM-DD.log dosyasına da yazılır.
"""
import argparse
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PROJE = Path(__file__).resolve().parent
LOGLAR = PROJE / "loglar"

GUNLUK_CEKIM = ["siparisler", "urunler", "sorular", "iadeler", "finans"]
HAFTALIK_CEKIM = ["yorumlar"]   # resmi olmayan uç nokta, sık kullanılmamalı
HAZIRLAMA = [("temizle", ["hazirlama/temizle.py"]),
             ("analiz", ["hazirlama/ozellik_cikar.py", "gercek"])]


def calistir(ad, komut, log):
    print(f"\n=== {ad} ===", flush=True)
    log.write(f"\n=== {ad} ({datetime.now():%H:%M:%S}) ===\n")
    log.flush()
    bas = time.time()
    surec = subprocess.Popen([sys.executable, *komut], cwd=PROJE, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                             env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    for satir in surec.stdout:
        print(satir, end="", flush=True)
        log.write(satir)
    basarili = surec.wait() == 0
    sure = time.time() - bas
    durum = "tamam" if basarili else f"HATA (çıkış kodu {surec.returncode})"
    log.write(f"--- {ad}: {durum}, {sure:.0f} sn\n")
    return ad, basarili, sure


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--haftalik", action="store_true", help="haftalık çekimleri (yorumlar) de çalıştır")
    p.add_argument("--sadece", help="yalnızca bu çekimler, virgülle: " + ",".join(GUNLUK_CEKIM + HAFTALIK_CEKIM))
    p.add_argument("--cekmeden", action="store_true", help="API'ye istek atmadan yalnızca temizleme ve analiz")
    p.add_argument("--sahte", action="store_true",
                   help="yalnızca sahte veri için analiz tabloları (ekip üyeleri için; .env ve gerçek veri gerekmez)")
    p.add_argument("--uretmeden", action="store_true", help="panel çıktılarını (calistir.py) üretme")
    args = p.parse_args()

    if args.sahte:
        cekimler = []
    elif args.cekmeden:
        cekimler = []
    elif args.sadece:
        cekimler = [c.strip() for c in args.sadece.split(",")]
        bilinmeyen = set(cekimler) - set(GUNLUK_CEKIM + HAFTALIK_CEKIM)
        if bilinmeyen:
            p.error(f"bilinmeyen çekim: {', '.join(bilinmeyen)}")
    else:
        cekimler = GUNLUK_CEKIM + (HAFTALIK_CEKIM if args.haftalik or datetime.now().weekday() == 0 else [])

    if args.sahte:
        adimlar = [("sahte_analiz", ["hazirlama/ozellik_cikar.py", "sahte"])]
    else:
        adimlar = [(c, ["-m", f"cekim.{c}"]) for c in cekimler] + HAZIRLAMA
    if not args.uretmeden:
        adimlar.append(("uretim", ["calistir.py", "--veri", "sahte" if args.sahte else "gercek"]))
    LOGLAR.mkdir(exist_ok=True)
    log_yolu = LOGLAR / f"guncelle_{datetime.now():%Y-%m-%d}.log"
    with open(log_yolu, "a", encoding="utf-8") as log:
        log.write(f"\n##### {datetime.now():%Y-%m-%d %H:%M:%S} — {', '.join(a for a, _ in adimlar)}\n")
        sonuclar = [calistir(ad, komut, log) for ad, komut in adimlar]
        ozet = "\n".join(f"  {'✓' if ok else '✗'} {ad:12s} {sure:5.0f} sn" for ad, ok, sure in sonuclar)
        log.write(f"\nÖZET\n{ozet}\n")

    print(f"\nÖZET\n{ozet}\nLog: {log_yolu.relative_to(PROJE).as_posix()}")
    sys.exit(0 if all(ok for _, ok, _ in sonuclar) else 1)


if __name__ == "__main__":
    main()
