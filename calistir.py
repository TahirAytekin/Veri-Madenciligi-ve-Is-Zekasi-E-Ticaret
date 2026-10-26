"""Uçtan uca üretim hattı (F6-01): temiz veriden panelin okuduğu tüm çıktılar.

    python calistir.py --veri gercek        # veya sahte; ikisi için: --veri hepsi
    python calistir.py --veri sahte --sadece stok,tavsiye

Sırayla: kalıp tablosu (F2-04) → stok tablosu (F2-05) → yorum analizi (F2-06) → durum raporu (F1-03) → tavsiyeler
ve aksiyon planı (F3) → ürün kartları (F3-05) → asistan bilgi tabanı ve arama indeksi (F4).

Modeller burada YENİDEN EĞİTİLMEZ ve doğrulama sonuçları YAZILMAZ: model doğrulaması (docs/rapor/02_dogrulama.md)
önceden kayıtlı ve 25.10.2026 verisiyle dondurulmuş bir sonuçtur; yeni veriyle sessizce değişmemeli. Eğitilmiş model
dosyası yoksa (yalnızca F2-05) ilgili modülün eğitimi bir kez çalıştırılır. Her adım ayrı ölçülür; biri hata verirse
diğerleri devam eder. Özet: ciktilar/<veri>/uretim.json (panel "son güncelleme" olarak gösterir).
"""
import argparse
import json
import subprocess
import sys
import time
import traceback
from datetime import datetime

from hazirlama.ortak import PROJE, VERI
from modeller.ortak.degerlendir import CIKTILAR
from modeller.ortak.kayit import tahmin_kaydet

# ====================================================
# 1) ADIMLAR
# ====================================================

def kalip(veri):
    from modeller import beden_uyumu
    t = beden_uyumu.kalip_tablosu(veri)
    tahmin_kaydet(t, f"{beden_uyumu.MODEL_ID}_kalip", veri)
    return f"{len(t)} ürün, {int(t.kalip.isin(['dar', 'bol']).sum())} dar/bol"


def stok(veri):
    from modeller import talep
    from modeller.ortak.kayit import model_yukle
    yol = CIKTILAR / "modeller" / f"{talep.MODEL_ID}.joblib"
    if not yol.exists():                                   # yalnızca ilk kurulumda: model sahteyle bir kez eğitilir
        subprocess.run([sys.executable, "-m", "modeller.talep"], cwd=PROJE, check=True, capture_output=True)
    t = talep.stok_tablosu(veri, model_yukle(talep.MODEL_ID)["model"])
    tahmin_kaydet(t, f"{talep.MODEL_ID}_stok", veri)
    kritik = t[~t.temsili_stok.astype(bool) & (t.haftalik_hiz >= 1) & (t.stok_hafta < 3)]
    return f"{len(t)} aktif ürün, {len(kritik)} çok satan ürünün stoğu 3 haftadan kısa"


def yorum(veri):
    from modeller import duygu
    y = duygu.skorla(veri)
    tahmin_kaydet(y.drop(columns=["yorum"]).round(4), duygu.MODEL_ID, veri)
    tahmin_kaydet(duygu.urun_ozeti(y), f"{duygu.MODEL_ID}_urun", veri)
    return f"{len(y)} yorum, %{y.sikayet_iceriyor.mean() * 100:.0f} şikâyetli"


def durum(veri):
    from analiz import durum as d
    r = d.kaydet(veri)
    return f"sağlık skoru {r['saglik_skoru']['skor']:.0f}, {len(r['icgoruler'])} içgörü"


def tavsiye(veri):
    from tavsiye import motor
    liste, plan, hatalar = motor.calistir(veri)
    ek = f", {len(hatalar)} kural hatası" if hatalar else ""
    etki = f"{plan['toplam_aylik_etki_tl']:,.0f}".replace(",", ".")
    return f"{len(liste)} tavsiye, planın aylık etkisi {etki} TL{ek}"


def kart(veri):
    from tavsiye import urun_karti
    k, _ = urun_karti.calistir(veri)
    return f"{len(k)} ürün kartı"


def bilgi(veri):
    from asistan import arama, bilgi_tabani
    p = bilgi_tabani.kaydet(veri)
    arama.gommeler(veri, p, arama.SECILEN)                 # parçalar değiştiyse indeks burada yenilenir
    return f"{len(p)} parça, indeks {arama.SECILEN}"


ADIMLAR = {"kalip": kalip, "stok": stok, "yorum": yorum, "durum": durum, "tavsiye": tavsiye, "kart": kart,
           "bilgi": bilgi}


# ====================================================
# 2) ÇALIŞTIR
# ====================================================

def veri_setleri():
    return [v for v in ("sahte", "gercek") if (VERI / v / "siparisler.csv").exists()]


def calistir(veri, adimlar=None):
    from analiz import metrikler as m
    from modeller.ortak import ozellikler
    m.yenile()                                             # aynı süreçte önceki veri kalmasın
    ozellikler.iade_veri_seti.cache_clear()
    sonuclar = []
    for ad in adimlar or ADIMLAR:
        bas = time.time()
        try:
            sonuclar.append({"adim": ad, "durum": "tamam", "bilgi": ADIMLAR[ad](veri)})
        except Exception as e:                             # noqa: BLE001 — bir adımın hatası diğerlerini durdurmaz
            sonuclar.append({"adim": ad, "durum": "hata", "bilgi": f"{type(e).__name__}: {e}",
                             "iz": traceback.format_exc(limit=4)})
        sonuclar[-1]["sure_sn"] = round(time.time() - bas, 1)
        s = sonuclar[-1]
        print(f"  {'✓' if s['durum'] == 'tamam' else '✗'} {veri:6s} {ad:8s} {s['sure_sn']:5.1f} sn  {s['bilgi']}",
              flush=True)
    bas_, bit_ = m.veri_araligi(veri)
    ozet = {"veri": veri, "zaman": datetime.now().isoformat(timespec="seconds"),
            "veri_araligi": {"baslangic": str(bas_.date()), "bitis": str(bit_.date())},
            "basarili": all(s["durum"] == "tamam" for s in sonuclar), "adimlar": sonuclar}
    (CIKTILAR / veri).mkdir(parents=True, exist_ok=True)
    (CIKTILAR / veri / "uretim.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=2), encoding="utf-8")
    return ozet


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--veri", default="hepsi", choices=["sahte", "gercek", "hepsi"])
    p.add_argument("--sadece", help="yalnızca bu adımlar, virgülle: " + ",".join(ADIMLAR))
    a = p.parse_args()
    adimlar = [x.strip() for x in a.sadece.split(",")] if a.sadece else None
    if adimlar and set(adimlar) - set(ADIMLAR):
        p.error(f"bilinmeyen adım: {', '.join(set(adimlar) - set(ADIMLAR))}")
    veriler = veri_setleri() if a.veri == "hepsi" else [a.veri]
    if not all((VERI / v / "siparisler.csv").exists() for v in veriler):
        p.error(f"veri yok: {veriler}")
    ozetler = [calistir(v, adimlar) for v in veriler]
    sys.exit(0 if all(o["basarili"] for o in ozetler) else 1)


if __name__ == "__main__":
    main()
