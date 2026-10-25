"""Ürün sağlık kartı (F3-05): ürün başına satış, trend, katkı, iade, kalıp, müşteri sesi, stok ve ilgili tavsiyeler.

    python -m tavsiye.urun_karti --veri gercek                 # tüm kartlar -> ciktilar/<veri>/urun_kartlari.json
    python -m tavsiye.urun_karti --veri sahte --model esf01    # tek kart (ekrana)

    from tavsiye.urun_karti import kartlar
    k = kartlar("sahte")["esf01"]

Birim ekonomisi tavsiye motoruyla aynıdır (tavsiye/kurallar.py, son 90 gün); kart ile tavsiyeler aynı sayıları gösterir.
Model çıktıları (F2-04 kalıp, F2-05 stok, F2-06 yorum) yoksa ilgili bölüm boş kalır.

Etiketler ve genel durum (eşikler ETIKET_ESIK):
    sorunlu: zarar, iade oranı mağazanın 1,5 katı, şikâyetli, stok 1 haftadan kısa (haftada ≥ 1 satan ürün)
    dikkat : kalıbı dar/bol, satış düşüşü, ölü stok, stok 3 haftadan kısa, iade artışı
Temsili (sembolik, ≥ 900) stoklu ürünlerde stok etiketi üretilmez (modeller/talep.py, TEMSILI_STOK).
"""
import argparse
import json
import math

import numpy as np
import pandas as pd

from analiz import metrikler as m
from hazirlama.ortak import VERI
from modeller.ortak.degerlendir import CIKTILAR
from tavsiye import motor
from tavsiye.kurallar import ESIK, birim_katki

TREND_GUN = 30
HAFTA_SAYISI = 12
ETIKET_ESIK = {"trend_dusus": -0.30, "trend_artis": 0.30, "trend_min_adet": 10, "olu_stok_hafta": 4, "stok_kritik": 1,
               "stok_az": 3}
SORUNLU = {"zarar", "yuksek_iade", "sikayetli", "stok_kritik"}
DIKKAT = {"kalip_dar", "kalip_bol", "satis_dusuyor", "olu_stok", "stok_az", "iade_artisi"}


# ====================================================
# 1) BÖLÜMLER
# ====================================================

def _sayi(x, n=4):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return round(float(x), n)


def _satis_trendi(veri, bit):
    """Son 30 gün ve önceki 30 gün adet/ciro (sipariş tarihi, iptaller hariç)."""
    s = m.cerceveler(veri)["satis"]
    g = s[~s.iptal & s.model_kodu.notna()]
    son = g[g.siparis_tarihi > bit - pd.Timedelta(days=TREND_GUN)]
    once = g[(g.siparis_tarihi <= bit - pd.Timedelta(days=TREND_GUN))
             & (g.siparis_tarihi > bit - pd.Timedelta(days=2 * TREND_GUN))]
    a = son.groupby("model_kodu").agg(adet_30=("adet", "sum"), ciro_30=("satir_net_tutar", "sum"))
    o = once.groupby("model_kodu").agg(adet_onceki_30=("adet", "sum"), ciro_onceki_30=("satir_net_tutar", "sum"))
    t = a.join(o, how="outer").fillna(0)
    t["ciro_degisimi"] = np.where(t.ciro_onceki_30 > 0, t.ciro_30 / t.ciro_onceki_30.replace(0, np.nan) - 1, np.nan)
    return t


def _haftalik(veri):
    """Son HAFTA_SAYISI tam haftanın teslim edilen satış adedi (F2-05 serisi)."""
    from modeller.talep import haftalik_seri
    d = haftalik_seri(veri)
    son = d.hafta.max()
    d = d[d.hafta > son - pd.Timedelta(weeks=HAFTA_SAYISI)]
    return {k: g.set_index("hafta").adet.reindex(pd.date_range(son - pd.Timedelta(weeks=HAFTA_SAYISI - 1), son,
                                                                freq="7D"), fill_value=0).astype(int).tolist()
            for k, g in d.groupby("model_kodu")}, [str(h.date()) for h in pd.date_range(
                son - pd.Timedelta(weeks=HAFTA_SAYISI - 1), son, freq="7D")]


def _tablo(b, ad, anahtar="model_kodu"):
    t = b.cikti(ad)
    return {} if t is None else {r[anahtar]: r for r in t.to_dict("records")}


def _etiketler(kart, magaza_iade, iade_artisi):
    e = []
    k, i, st, ms = kart["karlilik"], kart["iade"], kart["stok"], kart["musteri_sesi"]
    if k.get("katki_payi_90") is not None and k["katki_payi_90"] < 0 and kart["satis"]["adet_90"] >= ESIK["zarar_adet"]:
        e.append("zarar")
    if i.get("oran") is not None and i["oran"] >= magaza_iade * ESIK["iade_kat"]:
        e.append("yuksek_iade")
    if kart["model_kodu"] in iade_artisi:
        e.append("iade_artisi")
    if kart["kalip"].get("etiket") in ("dar", "bol"):
        e.append(f"kalip_{kart['kalip']['etiket']}")
    if ms.get("yorum", 0) >= ESIK["min_yorum"] and (
            (ms.get("sikayetli_yorum_payi") or 0) >= ESIK["sikayet_payi"]
            or (ms.get("ortalama_puan") or 5) < ESIK["dusuk_puan"]):
        e.append("sikayetli")
    s = kart["satis"]
    if s["adet_onceki_30"] >= ETIKET_ESIK["trend_min_adet"] and s["ciro_degisimi"] is not None:
        if s["ciro_degisimi"] <= ETIKET_ESIK["trend_dusus"]:
            e.append("satis_dusuyor")
        elif s["ciro_degisimi"] >= ETIKET_ESIK["trend_artis"]:
            e.append("satis_artiyor")
    if st.get("stok") is not None and not st.get("temsili"):        # temsili (sembolik) stokta stok etiketi yok
        hafta, hiz = st.get("stok_hafta"), st.get("haftalik_hiz") or 0
        son4 = sum(s["haftalik_adet"][-ETIKET_ESIK["olu_stok_hafta"]:]) if s["haftalik_adet"] else 0
        if st["stok"] > 0 and son4 == 0:
            e.append("olu_stok")
        elif hiz >= 1 and hafta is not None and hafta < ETIKET_ESIK["stok_kritik"]:
            e.append("stok_kritik")
        elif hiz >= 1 and hafta is not None and hafta < ETIKET_ESIK["stok_az"]:
            e.append("stok_az")
    return e


def genel_durum(etiketler):
    if SORUNLU & set(etiketler):
        return "sorunlu"
    return "dikkat" if DIKKAT & set(etiketler) else "iyi"


# ====================================================
# 2) KARTLAR
# ====================================================

def kartlar(veri="sahte", tavsiye_listesi=None):
    """{model_kodu: kart}. Kartı olanlar: son 90 günde satışı olan veya stok/yorum kaydı olan ürünler."""
    if tavsiye_listesi is None:
        tavsiye_listesi, _, b = motor.tavsiyeler(veri)
    else:
        from tavsiye.kurallar import Baglam
        b = Baglam(veri)
    e = b.ekonomi
    trend = _satis_trendi(veri, b.bit)
    haftalik, haftalar = _haftalik(veri)
    kalip, stok, yorum = _tablo(b, "F2-04_kalip"), _tablo(b, "F2-05_stok"), _tablo(b, "F2-06_urun")
    urun = m.tablolar(veri)["urunler"].dropna(subset=["model_kodu"]).groupby("model_kodu").agg(
        kategori=("kategori", "first"), satista=("satista", "max"), varyant=("barkod", "nunique"))
    tav = {}
    for t in tavsiye_listesi:
        for k in t.ilgili.get("model_kodu", []):
            tav.setdefault(k, []).append({"id": t.id, "tur": t.tur, "baslik": t.baslik, "aksiyon": t.aksiyon,
                                          "etki_tl": _sayi(t.etki_tl, 0), "guven": t.guven})
    iade_artisi = {t.ilgili["model_kodu"][0] for t in tavsiye_listesi if t.tur == "iade_artisi"}
    magaza_iade = b.baz["iade_orani"]

    kodlar = sorted(set(e.index) | set(stok) | set(yorum))
    sonuc = {}
    for k in kodlar:
        r = e.loc[k] if k in e.index else None
        tr = trend.loc[k] if k in trend.index else None
        kart = {
            "model_kodu": k, "ad": b.ad(k),
            "kategori": urun.kategori.get(k) if k in urun.index else None,
            "satista": bool(urun.satista.get(k)) if k in urun.index and pd.notna(urun.satista.get(k)) else None,
            "satis": {"adet_90": _sayi(r.adet if r is not None else 0, 0),
                      "ciro_90": _sayi(r.ciro_net if r is not None else 0, 0),
                      "adet_30": _sayi(tr.adet_30 if tr is not None else 0, 0),
                      "ciro_30": _sayi(tr.ciro_30 if tr is not None else 0, 0),
                      "adet_onceki_30": _sayi(tr.adet_onceki_30 if tr is not None else 0, 0),
                      "ciro_degisimi": _sayi(tr.ciro_degisimi) if tr is not None else None,
                      "haftalik_adet": haftalik.get(k, [])},
            "karlilik": {} if r is None else {
                "katki_payi_90": _sayi(r.katki_payi, 0), "katki_marji": _sayi(r.katki_marji),
                "birim_net_fiyat": _sayi(r.P, 2), "birim_katki": _sayi(birim_katki(r.P, r.r, r.k, r.c, b.ik), 2),
                "indirim_orani": _sayi(r.indirim_orani), "komisyon_orani": _sayi(r.k)},
            "iade": {} if r is None else {
                "oran": _sayi(r.r_olcum), "magaza_orani": _sayi(magaza_iade),
                "olgun_teslim": _sayi(r.olgun_teslim_adet, 0), "beden_payi": _sayi(r.beden_payi)},
            "kalip": {} if k not in kalip else {
                "etiket": kalip[k]["kalip"], "skor": _sayi(kalip[k]["kalip_skoru"]),
                "beden_iadesi": _sayi(kalip[k]["beden_iadesi"], 0)},
            "musteri_sesi": {} if k not in yorum else {
                "yorum": int(yorum[k]["yorum"]), "ortalama_puan": _sayi(yorum[k]["ortalama_puan"], 2),
                "sikayetli_yorum_payi": _sayi(yorum[k]["sikayetli_yorum_payi"]),
                "en_sik_sikayet": yorum[k]["en_sik_sikayet"] if isinstance(yorum[k]["en_sik_sikayet"], str) else None},
            "stok": {} if k not in stok else {
                "stok": _sayi(stok[k]["stok"], 0), "temsili": bool(stok[k].get("temsili_stok")),
                "haftalik_hiz": _sayi(stok[k]["haftalik_hiz"], 2), "stok_hafta": _sayi(stok[k]["stok_hafta"], 1),
                "tukenme_tarihi": str(stok[k]["tukenme_tarihi"]) if pd.notna(stok[k]["stok_hafta"]) else None},
            "tavsiyeler": tav.get(k, []),
        }
        kart["etiketler"] = _etiketler(kart, magaza_iade, iade_artisi)
        kart["durum"] = genel_durum(kart["etiketler"])
        sonuc[k] = kart
    return sonuc, {"donem": b.donem(), "haftalar": haftalar, "magaza_iade_orani": magaza_iade}


def ozet(kart_listesi):
    d = pd.Series([k["durum"] for k in kart_listesi.values()]).value_counts().to_dict()
    etiket = pd.Series([e for k in kart_listesi.values() for e in k["etiketler"]]).value_counts().to_dict()
    return {"urun": len(kart_listesi), "durum": d, "etiketler": etiket}


def calistir(veri="sahte"):
    liste, _, _ = motor.tavsiyeler(veri)
    k, bilgi = kartlar(veri, liste)
    yol = CIKTILAR / veri / "urun_kartlari.json"
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps({**bilgi, "ozet": ozet(k), "kartlar": list(k.values())}, ensure_ascii=False, indent=1,
                              default=float), encoding="utf-8")
    return k, bilgi


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--veri", default="sahte", choices=["sahte", "gercek"])
    p.add_argument("--model", help="yalnızca bu ürünün kartı (ekrana)")
    a = p.parse_args()
    if not (VERI / a.veri / "siparisler.csv").exists():
        sys.exit(f"veri yok: {a.veri}")
    k, bilgi = calistir(a.veri)
    if a.model:
        print(json.dumps(k[a.model], ensure_ascii=False, indent=1, default=float))
    else:
        print(json.dumps(ozet(k), ensure_ascii=False, indent=1))
