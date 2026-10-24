"""Çekim betiklerinin ortak ayarları: .env okuma, kimlik doğrulama, dayanıklı istek, dosya okuma/yazma."""
import base64
import csv
import gzip
import json
import os
import sys
import time
from datetime import timedelta
from pathlib import Path

import requests

PROJE = Path(__file__).resolve().parent.parent
HAM = PROJE / "veri" / "ham"
API = "https://apigw.trendyol.com/integration"

sys.stdout.reconfigure(encoding="utf-8")


# ====================================================
# 1) .ENV
# ====================================================

def env_yukle(yol=PROJE / ".env"):
    """.env dosyasını ortam değişkenlerine yükler (ek paket gerektirmez). Tanımlı değişkenler ezilmez."""
    if not yol.exists():
        return
    for satir in yol.read_text(encoding="utf-8").splitlines():
        satir = satir.strip()
        if not satir or satir.startswith("#") or "=" not in satir:
            continue
        anahtar, deger = satir.split("=", 1)
        os.environ.setdefault(anahtar.strip(), deger.strip().strip("\"'"))


def gerekli(ad):
    deger = os.environ.get(ad)
    if not deger:
        sys.exit(f"{ad} tanımlı değil. Proje klasöründeki .env dosyasını kontrol edin (örnek: .env.example).")
    return deger


env_yukle()
SATICI_ID = gerekli("TRENDYOL_SATICI_ID")


def resmi_basliklar(**ek):
    """Trendyol entegrasyon API'si için Basic Auth başlıkları."""
    kimlik = base64.b64encode(f"{gerekli('TRENDYOL_API_KEY')}:{gerekli('TRENDYOL_API_SECRET')}".encode()).decode()
    return {"Authorization": f"Basic {kimlik}", "User-Agent": f"{SATICI_ID} - SelfIntegration", **ek}


# ====================================================
# 2) İSTEK
# ====================================================

def istek(url, params=None, headers=None, bekle=0.3, deneme_sayisi=5):
    """GET isteği; zaman aşımı, 429 (çok fazla istek) ve 5xx hatalarında artan beklemeyle tekrar dener."""
    for deneme in range(deneme_sayisi):
        try:
            yanit = requests.get(url, headers=headers, params=params, timeout=60)
        except requests.exceptions.RequestException as hata:
            print(f"  Bağlantı hatası ({type(hata).__name__}), tekrar deneniyor...")
            time.sleep(5 * (deneme + 1))
            continue
        if yanit.status_code == 429 or yanit.status_code >= 500:
            print(f"  HTTP {yanit.status_code}, bekleniyor...")
            time.sleep(5 * (deneme + 1))
            continue
        if yanit.status_code != 200:
            raise RuntimeError(f"HTTP {yanit.status_code}: {yanit.text[:500]}")
        time.sleep(bekle)
        return yanit.json()
    raise RuntimeError(f"İstek {deneme_sayisi} denemede başarısız oldu: {url}")


def tum_sayfalar(url, params, headers, boyut=200):
    """Sayfalı bir uç noktanın tüm sayfalarını birleştirir. Boş dönemlerde içerik None gelebilir."""
    satirlar, sayfa = [], 0
    while True:
        veri = istek(url, {**params, "page": sayfa, "size": boyut}, headers)
        satirlar.extend(veri.get("content") or [])
        sayfa += 1
        if sayfa >= (veri.get("totalPages") or 0):
            return satirlar


def ms(zaman):
    return int(zaman.timestamp() * 1000)


def pencereler(bitis, baslangic, gun):
    """bitis'ten baslangic'a doğru en fazla `gun` günlük (bas, bit) aralıkları üretir."""
    while bitis > baslangic:
        bas = max(bitis - timedelta(days=gun), baslangic)
        yield bas, bitis
        bitis = bas


# ====================================================
# 3) DOSYA
# ====================================================
# Yazma işlemleri önce geçici dosyaya yapılır: çekim yarıda kesilirse eski veri bozulmaz.

def _yerine_koy(gecici, hedef):
    gecici.replace(hedef)
    print(f"Kaydedildi: {hedef.relative_to(PROJE).as_posix()}")


def json_oku(ad, varsayilan=None):
    yol = HAM / ad
    if not yol.exists():
        return varsayilan
    with open(yol, encoding="utf-8") as f:
        return json.load(f)


def json_yaz(ad, veri):
    HAM.mkdir(parents=True, exist_ok=True)
    gecici = HAM / f".{ad}.tmp"
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False)
    _yerine_koy(gecici, HAM / ad)


def csv_oku(ad):
    yol = HAM / ad
    if not yol.exists():
        return []
    with open(yol, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def csv_yaz(ad, satirlar, sikistir=False):
    hedef = HAM / ad
    hedef.parent.mkdir(parents=True, exist_ok=True)
    gecici = hedef.with_name(f".{hedef.name}.tmp")
    acici = gzip.open if sikistir else open
    with acici(gecici, "wt", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(satirlar[0].keys()) if satirlar else ["bos"])
        writer.writeheader()
        writer.writerows(satirlar)
    _yerine_koy(gecici, hedef)
