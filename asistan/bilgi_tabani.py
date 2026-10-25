"""Bilgi tabanı (F4-01): asistanın arayacağı metin parçaları.

    python -m asistan.bilgi_tabani --veri sahte      # -> ciktilar/<veri>/indeks/parcalar.jsonl

Kaynaklar (tur):
    metrik         39 metriğin tanımı, kırılımları ve son 90 günlük değeri (analiz/metrikler.py)
    belge          veri ve metrik sözlükleri, doğrulama yöntemi ve raporu, tavsiye kuralları, model kartları
    icgoru         durum raporu içgörüleri (analiz/durum.py)
    tavsiye        tavsiyeler: kanıt, aksiyon, etki, güven (tavsiye/motor.py)
    urun           ürün sağlık kartlarının metin hali (tavsiye/urun_karti.py)
    kategori       kategori başına son 90 günün özeti
    ay             ay başına ana metrikler
Sayılar araçlarla da hesaplanabilir; bilgi tabanındaki sayılar parçanın üretildiği andaki değerdir (dönem yazar).
Gerçek veriden üretilen parçalar ciktilar/gercek/ altında kalır, git'e girmez.
"""
import argparse
import json
import re

import pandas as pd

from analiz import durum
from analiz import metrikler as m
from analiz.durum import sayi, tl, yuzde
from hazirlama.ortak import PROJE, VERI
from modeller.ortak.degerlendir import CIKTILAR

EN_UZUN = 1500
BELGELER = ["docs/VERI_SOZLUGU.md", "docs/METRIKLER.md", "docs/MODEL_DOGRULAMA.md", "docs/TAVSIYE_KURALLARI.md",
            "docs/rapor/02_dogrulama.md", "docs/rapor/sahte_v2_kalibrasyon.md"]
OZET_METRIKLERI = ["ciro_net", "satilan_adet", "siparis_sayisi", "iade_orani", "katki_payi", "katki_marji",
                   "ortalama_puan"]
DONEM_GUN = 90


def _parca(id_, tur, baslik, metin, kaynak, **ilgili):
    return {"id": id_, "tur": tur, "baslik": baslik, "metin": metin.strip(), "kaynak": kaynak,
            "ilgili": {k: v for k, v in ilgili.items() if v}}


def _deger(ad, birim, x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "hesaplanamadı (yetersiz veri)"
    return {"TL": tl, "oran": yuzde}.get(birim, lambda v: sayi(v, 2 if birim in ("puan",) else 0))(x)


# ====================================================
# 1) KAYNAKLAR
# ====================================================

def metrik_parcalari(veri):
    bit = m.veri_araligi(veri)[1]
    bas = bit - pd.Timedelta(days=DONEM_GUN - 1)
    sonuc = []
    for r in m.metrik_listesi().itertuples():
        try:
            deger = _deger(r.ad, r.birim, m.hesapla(r.ad, veri, bas, bit))
        except Exception:                                    # noqa: BLE001 — değer yoksa tanım yine eklenir
            deger = "hesaplanamadı"
        sonuc.append(_parca(
            f"metrik:{r.ad}", "metrik", f"Metrik: {r.baslik} ({r.ad})",
            f"{r.baslik} ({r.ad}), birim: {r.birim}. Tanım: {r.aciklama}. İyi yön: {r.iyi_yon}. Kırılımlar: "
            f"{r.kirilimlar}. Son {DONEM_GUN} gün ({bas.date()} – {bit.date()}): {deger}.",
            "analiz/metrikler.py"))
    return sonuc


def _bol(metin, en_uzun=EN_UZUN):
    """Uzun bölümü paragraflardan böler."""
    parcalar, simdiki = [], ""
    for p in re.split(r"\n\s*\n", metin):
        if simdiki and len(simdiki) + len(p) > en_uzun:
            parcalar.append(simdiki)
            simdiki = ""
        simdiki = (simdiki + "\n\n" + p).strip()
    return parcalar + ([simdiki] if simdiki else [])


def belge_parcalari(yol):
    """Markdown belgesi başlıklara (#, ##, ###) göre bölünür; başlık yolu parçanın başlığı olur."""
    metin = (PROJE / yol).read_text(encoding="utf-8")
    sonuc, yollar, govde, baslik = [], {}, [], None

    def bitir():
        icerik = "\n".join(govde).strip()
        if icerik and baslik:
            for i, p in enumerate(_bol(icerik)):
                sonuc.append(_parca(f"belge:{yol}#{len(sonuc)}", "belge", baslik, p, yol))

    for satir in metin.splitlines():
        b = re.match(r"^(#{1,3})\s+(.*)", satir)
        if b:
            bitir()
            yollar = {k: v for k, v in yollar.items() if k < len(b.group(1))}
            yollar[len(b.group(1))] = b.group(2).strip()
            baslik, govde = " › ".join(yollar[k] for k in sorted(yollar)), []
        else:
            govde.append(satir)
    bitir()
    return sonuc


def belge_listesi():
    kartlar = sorted(p.relative_to(PROJE).as_posix() for p in (PROJE / "docs" / "modeller").glob("F*.md"))
    return [y for y in BELGELER if (PROJE / y).exists()] + kartlar


def icgoru_parcalari(veri):
    r = durum.durum_raporu(veri)
    sk = r["saglik_skoru"]
    bilesen = "; ".join(f"{b['baslik']} {sayi(b['puan'])}/100 ({b['metrik']} = {sayi(b['deger'], 3)})"
                        for b in sk["bilesenler"] if b["puan"] is not None)
    sonuc = [_parca("icgoru:saglik", "icgoru", f"Mağaza sağlık skoru {sayi(sk['skor'])}/100",
                    f"Mağazanın sağlık skoru {sayi(sk['skor'])}/100 (bileşenlerin ortalaması). Bileşenler: {bilesen}. "
                    f"Dönem: {r['donem']['baslangic']} – {r['donem']['bitis']}.", "analiz/durum.py")]
    for i in r["icgoruler"]:
        sonuc.append(_parca(f"icgoru:{i['id']}", "icgoru", i["baslik"],
                            f"{i['aciklama']} (önem: {i['onem']}, yön: {i['yon']})", "analiz/durum.py",
                            **{k: v for k, v in i.get("ilgili", {}).items()}))
    return sonuc


def tavsiye_parcalari(liste):
    sonuc = []
    for t in liste:
        etki = f"Beklenen etki: aylık {tl(t.etki_tl)} ({t.etki_aciklama})." if t.etki_tl is not None else \
            "Etkisi TL ile ölçülmedi."
        sonuc.append(_parca(
            f"tavsiye:{t.id}", "tavsiye", f"Tavsiye: {t.baslik}",
            f"{t.aciklama} Önerilen aksiyon: {t.aksiyon} {etki} Güven: {t.guven} ({t.guven_gerekcesi}). "
            f"Kaynak: {', '.join(t.kanit.get('kaynak', []))}.", "tavsiye/motor.py", **t.ilgili))
    return sonuc


def _kart_metni(k):
    s, kar, i, ka, ms, st = k["satis"], k["karlilik"], k["iade"], k["kalip"], k["musteri_sesi"], k["stok"]
    parca = [f"{k['ad']} (model kodu {k['model_kodu']}, kategori {k['kategori']}). Genel durum: {k['durum']}"
             + (f"; etiketler: {', '.join(k['etiketler'])}." if k["etiketler"] else ".")]
    parca.append(f"Son 90 gün: {sayi(s['adet_90'])} adet, net satış {tl(s['ciro_90'])}. Son 30 gün: "
                 f"{sayi(s['adet_30'])} adet" + (f", önceki 30 güne göre ciro değişimi {yuzde(s['ciro_degisimi'])}."
                                                 if s["ciro_degisimi"] is not None else "."))
    if kar:
        parca.append(f"Katkı payı {tl(kar['katki_payi_90'])}"
                     + (f", katkı marjı {yuzde(kar['katki_marji'])}" if kar["katki_marji"] is not None else "")
                     + f", birim net fiyat {tl(kar['birim_net_fiyat'])}, indirim oranı "
                     + (yuzde(kar["indirim_orani"]) if kar["indirim_orani"] is not None else "—") + ".")
    if i and i.get("oran") is not None:
        parca.append(f"İade oranı {yuzde(i['oran'])} (mağaza {yuzde(i['magaza_orani'])})"
                     + (f", iadelerin {yuzde(i['beden_payi'], 0)} kadarı beden kaynaklı." if i.get("beden_payi")
                        is not None else "."))
    if ka and ka["beden_iadesi"] >= 5:
        parca.append(f"Kalıp: {ka['etiket']} ({sayi(ka['beden_iadesi'])} beden iadesinin "
                     f"{yuzde(ka['skor'], 0)} kadarı 'küçük geldi').")
    elif ka:
        parca.append("Kalıp: yeterli beden iadesi yok (5'ten az).")
    if ms:
        parca.append(f"Yorumlar: {ms['yorum']} yorum, ortalama puan {sayi(ms['ortalama_puan'], 1)}, şikâyetli yorum "
                     f"payı {yuzde(ms['sikayetli_yorum_payi'], 0)}"
                     + (f", en sık şikâyet {ms['en_sik_sikayet']}." if ms.get("en_sik_sikayet") else "."))
    if st:
        parca.append("Stok: temsili (sembolik) stok." if st.get("temsili") else
                     f"Stok {sayi(st['stok'])} adet, haftalık satış hızı {sayi(st['haftalik_hiz'], 1)}"
                     + (f", yaklaşık {sayi(st['stok_hafta'], 1)} hafta yeter." if st.get("stok_hafta") is not None
                        else "."))
    if k["tavsiyeler"]:
        parca.append("Tavsiyeler: " + "; ".join(t["baslik"] for t in k["tavsiyeler"]) + ".")
    return " ".join(parca)


def urun_parcalari(kartlar):
    return [_parca(f"urun:{k}", "urun", f"Ürün kartı: {v['ad']}", _kart_metni(v), "tavsiye/urun_karti.py",
                   model_kodu=[k], kategori=[v["kategori"]] if v["kategori"] else None) for k, v in kartlar.items()]


def kategori_parcalari(veri):
    bit = m.veri_araligi(veri)[1]
    bas = bit - pd.Timedelta(days=DONEM_GUN - 1)
    t = pd.DataFrame({a: m.hesapla(a, veri, bas, bit, kirilim="kategori") for a in OZET_METRIKLERI[:-1]})
    puan = m.hesapla("ortalama_puan", veri, kirilim="kategori")
    sonuc = []
    for kat, r in t.iterrows():
        metin = (f"{kat} kategorisi, son {DONEM_GUN} gün ({bas.date()} – {bit.date()}): net satış {tl(r.ciro_net)}, "
                 f"{sayi(r.satilan_adet)} adet, {sayi(r.siparis_sayisi)} sipariş, iade oranı "
                 f"{_deger('iade_orani', 'oran', r.iade_orani)}, katkı payı {tl(r.katki_payi)}, katkı marjı "
                 f"{_deger('katki_marji', 'oran', r.katki_marji)}"
                 + (f", ortalama ürün puanı {sayi(puan[kat], 2)}" if kat in puan.index and pd.notna(puan[kat])
                    else "") + ".")
        sonuc.append(_parca(f"kategori:{kat}", "kategori", f"Kategori özeti: {kat}", metin, "analiz/metrikler.py",
                            kategori=[kat]))
    return sonuc


def ay_parcalari(veri):
    t = pd.DataFrame({a: m.hesapla(a, veri, kirilim="ay") for a in OZET_METRIKLERI[:-1]})
    sonuc = []
    for ay, r in t.iterrows():
        sonuc.append(_parca(
            f"ay:{ay}", "ay", f"Aylık özet: {ay}",
            f"{ay} ayı: net satış {tl(r.ciro_net)}, {sayi(r.satilan_adet)} adet, {sayi(r.siparis_sayisi)} sipariş, "
            f"iade oranı {_deger('iade_orani', 'oran', r.iade_orani)}, katkı payı {tl(r.katki_payi)}, katkı marjı "
            f"{_deger('katki_marji', 'oran', r.katki_marji)}.", "analiz/metrikler.py"))
    return sonuc


# ====================================================
# 2) OLUŞTUR
# ====================================================

def olustur(veri="sahte"):
    from tavsiye import motor, urun_karti
    liste, _, _ = motor.tavsiyeler(veri)
    kartlar, _ = urun_karti.kartlar(veri, liste)
    parcalar = (metrik_parcalari(veri) + [p for y in belge_listesi() for p in belge_parcalari(y)]
                + icgoru_parcalari(veri) + tavsiye_parcalari(liste) + urun_parcalari(kartlar)
                + kategori_parcalari(veri) + ay_parcalari(veri))
    for p in parcalar:
        p["veri"] = veri
    assert len({p["id"] for p in parcalar}) == len(parcalar), "parça kimlikleri tekil olmalı"
    return parcalar


def yol(veri):
    return CIKTILAR / veri / "indeks" / "parcalar.jsonl"


def kaydet(veri="sahte"):
    parcalar = olustur(veri)
    hedef = yol(veri)
    hedef.parent.mkdir(parents=True, exist_ok=True)
    hedef.write_text("\n".join(json.dumps(p, ensure_ascii=False, default=str) for p in parcalar) + "\n",
                     encoding="utf-8")
    return parcalar


def oku(veri="sahte"):
    return [json.loads(s) for s in yol(veri).read_text(encoding="utf-8").splitlines() if s.strip()]


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--veri", default="sahte", choices=["sahte", "gercek"])
    a = p.parse_args()
    if not (VERI / a.veri / "siparisler.csv").exists():
        sys.exit(f"veri yok: {a.veri}")
    parcalar = kaydet(a.veri)
    sayim = pd.Series([x["tur"] for x in parcalar]).value_counts().to_dict()
    uzunluk = pd.Series([len(x["metin"]) for x in parcalar])
    print(f"{len(parcalar)} parça · {sayim} · metin uzunluğu medyan {uzunluk.median():.0f}, en çok {uzunluk.max()}")
