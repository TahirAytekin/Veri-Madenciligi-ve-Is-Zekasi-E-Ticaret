"""Tavsiye kuralları (F3-02). Her kural bir Baglam alır ve 0 veya daha fazla Tavsiye döndürür.

Beklenen etki: aylık katkı payı farkı (TL, ürün maliyeti hariç), senaryo simülatörüyle (analiz/senaryo.py) aynı birim
modeliyle. Ürün başına birim katkı:
    u(P, r) = (1 − r) × P × (1 − k) − c − r × ik
    P birim net fiyat, r iade oranı, k komisyon oranı, c birim kargo + platform, ik iade başına kargo
Önlenen her iade katkıya P × (1 − k) + ik ekler. Varsayımlar (VARSAYIM) her tavsiyede gösterilir.

Girdi: analiz/metrikler.py çerçeveleri, senaryo.simule, model çıktıları ciktilar/<veri>/tahminler/ (F2-04_kalip,
F2-05_stok, F2-06_urun). Bir model çıktısı yoksa ona dayanan kural sessizce boş döner.
"""
import math
from itertools import combinations

import numpy as np
import pandas as pd

from analiz import metrikler as m
from analiz.durum import sayi, tl, yuzde
from analiz.senaryo import baz_degerler, simule
from modeller.ortak.degerlendir import CIKTILAR
from tavsiye.sema import Tavsiye, model_karari

DONEM_GUN = 90
AY = 30
VARSAYIM = {
    "kalip_notu_beden_iade_azalisi": 0.30,      # kalıp notu + beden tablosu, o ürünün beden iadelerini azaltır
    "beden_onerici_beden_iade_azalisi": 0.20,   # beden önerici tüm mağazada beden iadelerini azaltır
    "iade_riski_fark_kapanisi": 0.50,           # ürün iyileştirmesiyle mağaza ortalamasına farkın kapanan kısmı
    "fiyat_esnekligi": 1.5,                     # talep (1 + fiyat değişimi)^(−esneklik) katına çıkar
    "tedarik_hafta": 3,                         # stok siparişinin gelmesi
    "stok_hedef_hafta": 6,                      # siparişten sonra stok kaç hafta yetsin
    "kampanya_kuponu": 0.10,
}
ESIK = {"iade_kat": 1.5, "min_teslim": 30, "min_adet": 10, "zarar_adet": 10, "iade_artis_kat": 1.5,
        "iade_artis_puan": 0.05, "sikayet_payi": 0.5, "dusuk_puan": 3.5, "min_yorum": 3, "indirim_yuksek": 0.20,
        "marj_dusuk": 0.10, "marj_yuksek": 0.30, "indirim_dusuk": 0.05, "kampanya_stok_hafta": 8,
        "cevap_dk": 360, "cevapsiz": 0.10, "desi_tl": 1000, "capraz_destek": 5, "capraz_lift": 2.0,
        "sezon_kat": 1.3, "sezon_min_adet": 20, "kayip_gun": 45, "kayip_min": 10, "beden_payi": 0.40}
ESNEKLIK_GEREKCESI = ("Fiyat esnekliği varsayım: mağaza verisinden ölçülemedi (F2-10; kuponlar yavaş satan ürünlere "
                      "veriliyor).")
SIKAYET_AKSIYONU = {
    "beden_kalip": "beden tablosunu ve kalıp bilgisini ürün sayfasında öne çıkarın",
    "kumas_kalite": "tedarikçiyle kumaş/dikiş kalitesini görüşün; açıklamaya kumaş içeriğini ve kalınlığını yazın",
    "kargo_paket": "paketlemeyi güçlendirin; kargoya verilme süresini kontrol edin",
    "renk_gorsel": "ürün fotoğraflarını gün ışığında yeniden çekin; renk adını netleştirin",
    "fiyat": "fiyat/değer algısını kontrol edin: rakip fiyatları ve ürün açıklamasını gözden geçirin",
    "urun_hatasi": "gönderim öncesi kalite kontrolü ekleyin (leke, eksik parça, yanlış ürün)",
}


# ====================================================
# 1) BAĞLAM VE BİRİM EKONOMİSİ
# ====================================================

class Baglam:
    """Bir veri seti için ortak dönem, ürün ekonomisi ve model çıktıları."""

    def __init__(self, veri):
        self.veri = veri
        self.bit = m.veri_araligi(veri)[1]
        self.bas = self.bit - pd.Timedelta(days=DONEM_GUN - 1)
        self.gun = DONEM_GUN
        u = m.tablolar(veri)["urunler"].dropna(subset=["model_kodu"])
        self.model_adi = u.groupby("model_kodu").urun_adi.first().to_dict()
        self.baz = baz_degerler(veri, self.bas, self.bit)
        self.ekonomi = urun_ekonomisi(veri, self.bas, self.bit)
        self.ik = self.baz["iade_basi_kargo"]

    def ad(self, model_kodu):
        return self.model_adi.get(model_kodu, model_kodu)

    def cikti(self, ad):
        yol = CIKTILAR / self.veri / "tahminler" / f"{ad}.csv"
        return pd.read_csv(yol, encoding="utf-8-sig") if yol.exists() else None

    def aylik(self, x):
        return x * AY / self.gun

    def donem(self):
        return {"baslangic": str(self.bas.date()), "bitis": str(self.bit.date())}


def urun_ekonomisi(veri, bas, bit):
    """Model başına dönemin birim değerleri: adet, P, k, c, r (olgun satırlar), beden payı, katkı, indirim."""
    s = m.cerceveler(veri)["satis"]
    d = s[(s.siparis_tarihi >= bas) & (s.siparis_tarihi < bit + pd.Timedelta(days=1))]
    g = d[~d.iptal]
    t = g.groupby("model_kodu").agg(kategori=("kategori", "first"), adet=("adet", "sum"),
                                    ciro_net=("satir_net_tutar", "sum"), ciro_brut=("brut_tutar", "sum"),
                                    komisyon=("komisyon_tutari", "sum"), kargo=("kargo_payi", "sum"),
                                    platform=("platform_payi", "sum"), teslim=("teslim_adet", "sum"))
    t["kalan_net"] = (g.kalan_adet * g.birim_net_fiyat).groupby(g.model_kodu).sum()
    o = d.groupby("model_kodu")[["olgun_teslim_adet", "olgun_iade_adet", "olgun_beden_iade_adet", "katki_payi"]].sum()
    t = t.join(o)
    t["P"] = t.ciro_net / t.adet
    t["k"] = (t.komisyon / t.kalan_net.replace(0, np.nan)).fillna((g.komisyon_orani / 100).mean())
    t["c"] = (t.kargo + t.platform) / t.adet
    magaza_r = t.olgun_iade_adet.sum() / max(t.olgun_teslim_adet.sum(), 1)
    t["r_olcum"] = np.where(t.olgun_teslim_adet >= m.MIN_ORNEK, t.olgun_iade_adet / t.olgun_teslim_adet.clip(lower=1),
                            np.nan)
    t["r"] = t.r_olcum.fillna(magaza_r)                       # az örnekte mağaza oranı (birim ekonomisi için)
    t["beden_payi"] = np.where(t.olgun_iade_adet >= 5, t.olgun_beden_iade_adet / t.olgun_iade_adet.clip(lower=1),
                               np.nan)
    t["indirim_orani"] = 1 - t.ciro_net / t.ciro_brut.replace(0, np.nan)
    t["katki_marji"] = t.katki_payi / t.ciro_net.replace(0, np.nan)
    return t[t.adet > 0]


def birim_katki(P, r, k, c, ik):
    return (1 - r) * P * (1 - k) - c - r * ik


def onlenen_iade_degeri(P, k, ik):
    """Önlenen bir iadenin katkıya etkisi (senaryo modeli: iade edilen birim satış kaybı + iade kargosu)."""
    return P * (1 - k) + ik


def fiyat_etkisi(satir, f, ik, esneklik):
    """Net fiyat f katına çıkarsa (f < 1 indirim) dönemlik katkı farkı; adet f^(−esneklik) katına."""
    once = satir.adet * birim_katki(satir.P, satir.r, satir.k, satir.c, ik)
    sonra = satir.adet * f ** -esneklik * birim_katki(satir.P * f, satir.r, satir.k, satir.c, ik)
    return sonra - once


def _guven_model(model_id, basarili="orta", aksi="dusuk"):
    return basarili if model_karari(model_id) == "basarili" else aksi


# ====================================================
# 2) KURALLAR
# ====================================================

def stok_tukenme(b):
    s = b.cikti("F2-05_stok")
    if s is None:
        return []
    th, hedef = VARSAYIM["tedarik_hafta"], VARSAYIM["stok_hedef_hafta"]
    s = s[(s.stok_hafta < th) & (s.haftalik_hiz >= 1)]          # temsili stoklu ürünlerde stok_hafta boş
    s = s.join(b.ekonomi, on="model_kodu", rsuffix="_e")
    sonuc = []
    for r in s.itertuples():
        u = birim_katki(r.P, r.r, r.k, r.c, b.ik) if not math.isnan(getattr(r, "P", np.nan)) else \
            birim_katki(b.baz["birim_net_fiyat"], b.baz["iade_orani"], b.baz["komisyon_orani"],
                        b.baz["birim_kargo"] + b.baz["birim_platform"], b.ik)
        kayip = r.haftalik_hiz * max(0.0, 4 - r.stok_hafta)          # önümüzdeki 4 haftada satılamayacak adet
        siparis = math.ceil(max(r.haftalik_hiz * (th + hedef) - r.stok, 0))
        sonuc.append(Tavsiye(
            f"stok_tukenme:{r.model_kodu}", "stok_tukenme", "stok",
            f"{b.ad(r.model_kodu)}: stok {sayi(r.stok_hafta, 1)} haftada bitiyor",
            f"Stok {sayi(r.stok)} adet, son satış hızı haftada {sayi(r.haftalik_hiz, 1)} adet. Bu hızla stok "
            f"{sayi(r.stok_hafta, 1)} hafta yeter; tedarik {th} hafta sürerse arada satış kaçar.",
            f"{sayi(siparis)} adet sipariş verin (tedarik süresi + {hedef} hafta).",
            {"kaynak": ["F2-05_stok"], "stok": r.stok, "haftalik_hiz": r.haftalik_hiz, "stok_hafta": r.stok_hafta,
             "onerilen_siparis": siparis},
            "orta", "Stok gözlenen değer; satış hızı geçen haftadan (gerçek testte en iyi yöntem, ürün düzeyi "
            "WAPE 0,47).",
            "yuksek" if r.stok_hafta < 1 else "orta", u * kayip,
            f"4 haftada kaçacak {sayi(kayip)} adet × birim katkı {tl(u)}.",
            {k: VARSAYIM[k] for k in ("tedarik_hafta", "stok_hedef_hafta")}, {"model_kodu": [r.model_kodu]}))
    return sonuc


def kalip_uyarisi(b):
    t = b.cikti("F2-04_kalip")
    if t is None:
        return []
    t = t[t.kalip.isin(["dar", "bol"])].join(b.ekonomi, on="model_kodu", rsuffix="_e").dropna(subset=["P"])
    azalis = VARSAYIM["kalip_notu_beden_iade_azalisi"]
    sonuc = []
    for r in t.itertuples():
        kucuk = r.kalip == "dar"
        aylik_beden_iade = b.aylik(r.adet) * r.beden_iade_orani
        etki = aylik_beden_iade * azalis * onlenen_iade_degeri(r.P, r.k, b.ik)
        sonuc.append(Tavsiye(
            f"kalip_uyarisi:{r.model_kodu}", "kalip_uyarisi", "iade",
            f"{b.ad(r.model_kodu)}: kalıbı {r.kalip}",
            f"Beden iadelerinin {yuzde(r.kalip_skoru if kucuk else 1 - r.kalip_skoru, 0)} kadarı "
            f"'{'küçük' if kucuk else 'büyük'} geldi' ({sayi(r.beden_iadesi)} beden iadesi).",
            f"Ürün sayfasına 'kalıbı {r.kalip}, bir beden {'büyük' if kucuk else 'küçük'} alın' notu ve beden tablosu "
            "ekleyin; beden sorularına bu bilgiyle cevap verin.",
            {"kaynak": ["F2-04"], "kalip_skoru": r.kalip_skoru, "beden_iadesi": r.beden_iadesi,
             "beden_iade_orani": r.beden_iade_orani},
            "orta", "Kalıp skoru gerçekte beden iadesinin yönünü zayıf ayırıyor (AUC 0,59, sınırda); kanıt sayısı "
            "gösterilir.", "yuksek" if r.beden_iadesi >= 10 else "orta", etki,
            f"Aylık {sayi(aylik_beden_iade, 1)} beden iadesinin %{azalis * 100:.0f}'i önlenir × iade başına "
            f"{tl(onlenen_iade_degeri(r.P, r.k, b.ik))}.", {"kalip_notu_beden_iade_azalisi": azalis},
            {"model_kodu": [r.model_kodu]}))
    return sonuc


def beden_onerici(b):
    pay = b.baz["beden_payi"]
    if not pay or pay < ESIK["beden_payi"]:
        return []
    azalis = VARSAYIM["beden_onerici_beden_iade_azalisi"]
    s = simule(b.veri, b.bas, b.bit, beden_iade_azalis=azalis)
    return [Tavsiye(
        "beden_onerici", "beden_onerici", "iade", f"İadelerin {yuzde(pay, 0)} kadarı beden kaynaklı",
        f"Son {b.gun} günde iade oranı {yuzde(b.baz['iade_orani'])}; bunun {yuzde(pay, 0)} kadarı 'küçük/büyük geldi'.",
        "Beden önericiyi (boy + kilo → beden) ürün açıklamalarına ve beden sorularının cevaplarına ekleyin.",
        {"kaynak": ["F2-04C", "metrikler.beden_kaynakli_iade_payi"], "beden_payi": pay,
         "iade_orani": b.baz["iade_orani"]},
        _guven_model("F2-04C"), "Beden önerici gerçek müşterilerde en sık bedenden anlamlı biçimde iyi (F2-04C ✓); "
        "iade azalışı varsayım.", "yuksek", s["aylik_katki_farki"],
        f"Senaryo simülatörü: beden iadeleri %{azalis * 100:.0f} azalırsa.",
        {"beden_onerici_beden_iade_azalisi": azalis})]


def yuksek_iade_riski(b):
    e = b.ekonomi
    ort = b.baz["iade_orani"]
    secili = e[(e.r_olcum >= ort * ESIK["iade_kat"]) & (e.olgun_teslim_adet >= ESIK["min_teslim"])]
    kapanis = VARSAYIM["iade_riski_fark_kapanisi"]
    sonuc = []
    for k, r in secili.iterrows():
        beden_agirlikli = not math.isnan(r.beden_payi) and r.beden_payi >= 0.6
        etki = b.aylik(r.teslim) * (r.r_olcum - ort) * kapanis * onlenen_iade_degeri(r.P, r.k, b.ik)
        sonuc.append(Tavsiye(
            f"yuksek_iade_riski:{k}", "yuksek_iade_riski", "iade", f"{b.ad(k)}: iade oranı {yuzde(r.r_olcum)}",
            f"Mağaza ortalaması {yuzde(ort)}; bu üründe {sayi(r.olgun_teslim_adet)} teslimin "
            f"{sayi(r.olgun_iade_adet)} adedi iade edildi"
            + (f", iadelerin {yuzde(r.beden_payi, 0)} kadarı beden kaynaklı." if not math.isnan(r.beden_payi) else "."),
            ("Beden tablosu ve kalıp bilgisini düzeltin." if beden_agirlikli else
             "Ürün açıklamasını, fotoğrafları ve kaliteyi gözden geçirin; olumsuz yorumların konusuna bakın."),
            {"kaynak": ["metrikler.iade_orani", "F2-02"], "iade_orani": r.r_olcum, "magaza_iade_orani": ort,
             "teslim": r.olgun_teslim_adet, "beden_payi": None if math.isnan(r.beden_payi) else r.beden_payi},
            "yuksek", "Ürünün kendi geçmiş iade oranı gerçekte en güçlü iade göstergesi (F2-02 doğrulaması); "
            "iyileşme oranı varsayım.", "yuksek" if r.r_olcum >= 2 * ort else "orta", etki,
            f"Aylık {sayi(b.aylik(r.teslim))} teslimde mağaza ortalamasına farkın %{kapanis * 100:.0f}'i kapanırsa.",
            {"iade_riski_fark_kapanisi": kapanis}, {"model_kodu": [k], "kategori": [r.kategori]}))
    return sonuc


def zarar_eden_urun(b):
    e = b.ekonomi
    secili = e[(e.katki_payi < 0) & (e.adet >= ESIK["zarar_adet"])].sort_values("katki_payi")
    sonuc = []
    for k, r in secili.iterrows():
        u = r.katki_payi / r.adet                           # gözlenen birim katkı (negatif)
        artis = -u / ((1 - r.r) * (1 - r.k))                # fiyat Δ artınca birim katkı (1 − r)(1 − k)Δ artar
        sonuc.append(Tavsiye(
            f"zarar_eden_urun:{k}", "zarar_eden_urun", "karlilik", f"{b.ad(k)} zarar ettiriyor",
            f"Son {b.gun} günde {sayi(r.adet)} adet satıldı, katkı payı {tl(r.katki_payi)} (ürün maliyeti düşülmeden). "
            f"Birim fiyat {tl(r.P)}; iade, kargo ve komisyon satıştan fazla.",
            f"Net fiyatı en az {tl(artis)} (%{artis / r.P * 100:.0f}) artırın veya indirimden çıkarın; düzelmiyorsa "
            "satıştan kaldırın.",
            {"kaynak": ["metrikler.katki_payi"], "katki_payi": r.katki_payi, "adet": r.adet, "birim_katki": u,
             "basa_bas_fiyat_artisi": artis},
            "yuksek", "Mağazanın gözlenen satış, iade ve gider verisi.", "yuksek", -b.aylik(r.katki_payi),
            "Zararın durması (aylık).", {}, {"model_kodu": [k], "kategori": [r.kategori]}))
    return sonuc


def iade_artisi(b):
    s = m.cerceveler(b.veri)["satis"]
    sinir = s.siparis_tarihi.max() - pd.Timedelta(days=m.OLGUNLASMA_GUN)
    olgun = s[s.teslim_tarihi <= sinir]
    son = olgun[olgun.teslim_tarihi > sinir - pd.Timedelta(days=30)]
    once = olgun[(olgun.teslim_tarihi <= sinir - pd.Timedelta(days=30))
                 & (olgun.teslim_tarihi > sinir - pd.Timedelta(days=90))]
    sonuc = []

    def oran(d):
        return d.groupby("model_kodu")[["teslim_adet", "iade_adet"]].sum()

    a, o = oran(son), oran(once)
    t = a.join(o, lsuffix="_son", rsuffix="_once", how="inner")
    t = t[(t.teslim_adet_son >= ESIK["min_teslim"]) & (t.teslim_adet_once >= ESIK["min_teslim"])]
    t["r_son"], t["r_once"] = t.iade_adet_son / t.teslim_adet_son, t.iade_adet_once / t.teslim_adet_once
    t = t[(t.r_son >= t.r_once * ESIK["iade_artis_kat"]) & (t.r_son - t.r_once >= ESIK["iade_artis_puan"])]
    for k, r in t.iterrows():
        e = b.ekonomi.loc[k] if k in b.ekonomi.index else None
        deger = onlenen_iade_degeri(e.P, e.k, b.ik) if e is not None else None
        etki = None if deger is None else r.teslim_adet_son * (r.r_son - r.r_once) * deger
        sonuc.append(Tavsiye(
            f"iade_artisi:{k}", "iade_artisi", "iade", f"{b.ad(k)}: iade oranı {yuzde(r.r_once)} → {yuzde(r.r_son)}",
            f"Son 30 günde teslim edilen {sayi(r.teslim_adet_son)} adette iade oranı {yuzde(r.r_son)}; önceki "
            f"dönemde {yuzde(r.r_once)} ({sayi(r.teslim_adet_once)} teslim).",
            "Son partiyi (kumaş, dikiş, beden ölçüsü) kontrol edin; son iade notlarını ve yorumları okuyun.",
            {"kaynak": ["metrikler.iade_orani"], "iade_orani_son": r.r_son, "iade_orani_once": r.r_once,
             "teslim_son": r.teslim_adet_son, "teslim_once": r.teslim_adet_once},
            "orta", "Gözlenen değişim; örneklem küçük olabilir.", "yuksek", etki,
            "Oran önceki düzeyine dönerse (aylık).", {}, {"model_kodu": [k]}))
    return sonuc


def sikayetli_urun(b):
    t = b.cikti("F2-06_urun")
    if t is None:
        return []
    t = t[(t.yorum >= ESIK["min_yorum"])
          & ((t.sikayetli_yorum_payi >= ESIK["sikayet_payi"]) | (t.ortalama_puan < ESIK["dusuk_puan"]))]
    sonuc = []
    for r in t.itertuples():
        konu = r.en_sik_sikayet if isinstance(r.en_sik_sikayet, str) else None
        sonuc.append(Tavsiye(
            f"sikayetli_urun:{r.model_kodu}", "sikayetli_urun", "musteri_sesi",
            f"{b.ad(r.model_kodu)}: yorumların {yuzde(r.sikayetli_yorum_payi, 0)} kadarında şikâyet",
            f"{sayi(r.yorum)} yorum, ortalama puan {sayi(r.ortalama_puan, 1)}"
            + (f"; en sık şikâyet konusu: {konu.replace('_', '/')}." if konu else "."),
            (SIKAYET_AKSIYONU[konu].capitalize() + "." if konu in SIKAYET_AKSIYONU
             else "Olumsuz yorumları okuyup ortak sorunu bulun."),
            {"kaynak": ["F2-06"], "yorum": r.yorum, "ortalama_puan": r.ortalama_puan,
             "sikayetli_yorum_payi": r.sikayetli_yorum_payi, "en_sik_sikayet": konu},
            "orta", "BERT şikâyet tespiti gerçek yorumlarda iyi sıralıyor (AUC 0,91); konu kuralları doğrulanmadı.",
            "yuksek" if r.ortalama_puan < ESIK["dusuk_puan"] else "orta", None,
            "Etkisi TL ile ölçülmedi (puan → satış ilişkisi kurulmadı).", {}, {"model_kodu": [r.model_kodu]}))
    return sonuc


def marji_yiyen_indirim(b):
    e = b.ekonomi
    secili = e[(e.indirim_orani >= ESIK["indirim_yuksek"]) & (e.katki_marji < ESIK["marj_dusuk"])
               & (e.adet >= ESIK["min_adet"])]
    es = VARSAYIM["fiyat_esnekligi"]
    sonuc = []
    for k, r in secili.iterrows():
        f = (1 - r.indirim_orani / 2) / (1 - r.indirim_orani)         # indirimi yarıya indir
        etki = b.aylik(fiyat_etkisi(r, f, b.ik, es))
        if etki <= 0:
            continue
        sonuc.append(Tavsiye(
            f"marji_yiyen_indirim:{k}", "marji_yiyen_indirim", "fiyat",
            f"{b.ad(k)}: indirim %{r.indirim_orani * 100:.0f}, katkı marjı %{r.katki_marji * 100:.0f}",
            f"Son {b.gun} günde brüt fiyatın {yuzde(r.indirim_orani, 0)} kadarı indirim; kalan katkı marjı "
            f"{yuzde(r.katki_marji, 0)}.",
            f"İndirimi yarıya indirin (net fiyat %{(f - 1) * 100:.0f} artar); satış düşüşünü 2 hafta izleyin.",
            {"kaynak": ["metrikler.indirim_orani", "metrikler.katki_marji"], "indirim_orani": r.indirim_orani,
             "katki_marji": r.katki_marji, "adet": r.adet},
            "dusuk", ESNEKLIK_GEREKCESI, "orta", etki,
            f"Fiyat esnekliği {es} ile satış adedi ve birim katkı yeniden hesaplandı.", {"fiyat_esnekligi": es},
            {"model_kodu": [k]}))
    return sonuc


def kampanya_firsati(b):
    e = b.ekonomi
    stok = b.cikti("F2-05_stok")
    secili = e[(e.katki_marji >= ESIK["marj_yuksek"]) & (e.indirim_orani < ESIK["indirim_dusuk"])
               & (e.adet >= ESIK["min_adet"])]
    if stok is not None:
        yeterli = set(stok[stok.stok_hafta >= ESIK["kampanya_stok_hafta"]].model_kodu)
        secili = secili[secili.index.isin(yeterli)]
    sikayet = b.cikti("F2-06_urun")
    if sikayet is not None:
        secili = secili[~secili.index.isin(sikayet[sikayet.sikayetli_yorum_payi >= ESIK["sikayet_payi"]].model_kodu)]
    es, kupon = VARSAYIM["fiyat_esnekligi"], VARSAYIM["kampanya_kuponu"]
    sonuc = []
    for k, r in secili.iterrows():
        etki = b.aylik(fiyat_etkisi(r, 1 - kupon, b.ik, es))
        if etki <= 0:
            continue
        sonuc.append(Tavsiye(
            f"kampanya_firsati:{k}", "kampanya_firsati", "satis", f"{b.ad(k)}: kampanyaya uygun",
            f"Katkı marjı {yuzde(r.katki_marji, 0)}, indirim yalnızca {yuzde(r.indirim_orani, 0)}; stok yeterli.",
            f"%{kupon * 100:.0f} ürün kuponu tanımlayın; 2 hafta sonra satış artışını ölçün.",
            {"kaynak": ["metrikler.katki_marji", "metrikler.indirim_orani", "F2-05_stok"],
             "katki_marji": r.katki_marji, "indirim_orani": r.indirim_orani, "adet": r.adet},
            "dusuk", ESNEKLIK_GEREKCESI, "dusuk", etki,
            f"Fiyat esnekliği {es} ile %{kupon * 100:.0f} kuponun satış ve katkıya etkisi.",
            {"fiyat_esnekligi": es, "kampanya_kuponu": kupon}, {"model_kodu": [k]}))
    return sonuc


def geciken_cevap(b):
    bas = b.bit - pd.Timedelta(days=29)
    medyan = m.hesapla("medyan_cevap_suresi_dk", b.veri, bas, b.bit)
    cevapsiz = m.hesapla("cevaplanmamis_soru_orani", b.veri, bas, b.bit)
    beden = m.hesapla("beden_sorusu_orani", b.veri, bas, b.bit)
    gec, eksik = (medyan or 0) > ESIK["cevap_dk"], (cevapsiz or 0) > ESIK["cevapsiz"]
    if not (gec or eksik):
        return []
    return [Tavsiye(
        "geciken_cevap", "geciken_cevap", "operasyon",
        f"Müşteri soruları geç cevaplanıyor (medyan {sayi(medyan / 60, 1)} saat)",
        f"Son 30 günde medyan cevap süresi {sayi(medyan / 60, 1)} saat, cevaplanmamış soru oranı {yuzde(cevapsiz)}"
        + (f"; soruların {yuzde(beden, 0)} kadarı beden ile ilgili." if beden else "."),
        "Soruları günde iki kez cevaplayın; beden sorularında cevap önericiyi (boy-kilo → beden + kalıp) kullanın.",
        {"kaynak": ["metrikler.medyan_cevap_suresi_dk", "metrikler.cevaplanmamis_soru_orani"],
         "medyan_cevap_suresi_dk": medyan, "cevaplanmamis_soru_orani": cevapsiz, "beden_sorusu_orani": beden},
        "yuksek", "Mağazanın gözlenen soru-cevap verisi.", "yuksek" if gec and eksik else "orta", None,
        "Etkisi TL ile ölçülmedi.")]


def kargo_desisi(b):
    s = simule(b.veri, b.bas, b.bit, desi_azalis=1)
    if s["aylik_katki_farki"] < ESIK["desi_tl"]:
        return []
    return [Tavsiye(
        "kargo_desisi", "kargo_desisi", "kargo",
        f"Paketi 1 desi küçültmek ayda {tl(s['aylik_katki_farki'])} kazandırır",
        "Güncel kargo tarifesine göre her paketin 1 desi küçülmesi kargo giderini düşürüyor.",
        "Daha küçük poşet/kutu kullanın; ürünü katlayıp vakumlu paketlemeyi deneyin.",
        {"kaynak": ["senaryo.desi_azalis"], "aylik_katki_farki": s["aylik_katki_farki"]},
        "orta", "Senaryo simülatörü güncel tarifeyle; desi küçültmenin uygulanabilirliği varsayım.", "orta",
        s["aylik_katki_farki"], "Senaryo simülatörü: her gönderide 1 desi azalış.", {"desi_azalis": 1})]


def capraz_satis(b):
    s = m.cerceveler(b.veri)["satis"]
    g = s[~s.iptal & s.model_kodu.notna()]
    sepet = g.groupby("paket_id").model_kodu.agg(lambda x: tuple(sorted(set(x))))
    n = len(sepet)
    tek = sepet.explode().value_counts() / n
    ciftler = pd.Series([c for x in sepet if len(x) > 1 for c in combinations(x, 2)]).value_counts()
    ciftler = ciftler[ciftler >= ESIK["capraz_destek"]]
    sonuc = []
    for (a, c), say in ciftler.head(10).items():
        lift = (say / n) / (tek[a] * tek[c])
        if lift < ESIK["capraz_lift"]:
            continue
        sonuc.append(Tavsiye(
            f"capraz_satis:{a}+{c}", "capraz_satis", "satis", f"{b.ad(a)} + {b.ad(c)} birlikte alınıyor",
            f"{sayi(say)} sepette ikisi birlikte; rastlantıdan {sayi(lift, 1)} kat sık.",
            "İkisini 'birlikte al' kombini olarak sunun veya birini alana diğerinde kupon tanımlayın; ürün "
            "açıklamalarında birbirine bağlantı verin.",
            {"kaynak": ["siparis_satirlari"], "birlikte_sepet": int(say), "lift": lift, "sepet_sayisi": n},
            "orta", "Gözlenen sepetler; birliktelik nedensellik değildir.", "dusuk", None,
            "Etkisi TL ile ölçülmedi.", {}, {"model_kodu": [a, c]}))
        if len(sonuc) == 3:
            break
    return sonuc


def sezon_hazirligi(b):
    f = m.cerceveler(b.veri)["finans"]
    s = f[(f.islem_turu == "Satış") & f.kategori.notna()]
    if s.islem_tarihi.min() > b.bit - pd.Timedelta(days=364):
        return []                                                  # bir yıllık geçmiş yok
    gecen = s[(s.islem_tarihi > b.bit - pd.Timedelta(days=364)) & (s.islem_tarihi <= b.bit)]
    pencere = gecen[gecen.islem_tarihi <= b.bit - pd.Timedelta(days=364 - 42)]   # geçen yılın önümüzdeki 6 haftası
    yillik = gecen.groupby("kategori").size() / 52
    gelecek = pencere.groupby("kategori").size() / 6
    oran = (gelecek / yillik).dropna()
    secili = oran[(oran >= ESIK["sezon_kat"]) & (pencere.groupby("kategori").size().reindex(oran.index)
                                                  >= ESIK["sezon_min_adet"])]
    stok = b.cikti("F2-05_stok")
    sonuc = []
    for kat, k in secili.sort_values(ascending=False).items():
        kapsama = None
        if stok is not None:
            ks = stok[(stok.kategori == kat) & ~stok.temsili_stok.fillna(False).astype(bool)]
            kapsama = float(ks.stok.sum() / max(ks.haftalik_hiz.sum() * k, 0.01)) if len(ks) else None
        yetersiz = kapsama is not None and kapsama < 6
        sonuc.append(Tavsiye(
            f"sezon_hazirligi:{kat}", "sezon_hazirligi", "stok", f"{kat}: önümüzdeki 6 hafta sezon",
            f"Geçen yıl aynı 6 haftada {kat} satışı yıllık haftalık ortalamanın {sayi(k, 1)} katıydı."
            + (f" Bugünkü stok, bu artışla yaklaşık {sayi(kapsama, 1)} hafta yeter." if kapsama is not None else ""),
            f"{kat} kategorisinde stok ve yeni ürünleri şimdiden hazırlayın"
            + ("; mevcut stok sezona yetmiyor." if yetersiz else "."),
            {"kaynak": ["finans_hareketleri"], "sezon_kati": float(k), "stok_kapsama_hafta": kapsama},
            "orta", "Tek bir geçen yıla dayanıyor.", "yuksek" if yetersiz else "orta", None,
            "Etkisi TL ile ölçülmedi.", {}, {"kategori": [kat]}))
    return sonuc


def kayip_musteri(b):
    s = m.cerceveler(b.veri)["satis"]
    g = s[~s.iptal].groupby("musteri_id").agg(siparis=("siparis_no", "nunique"), son=("siparis_tarihi", "max"),
                                              ciro=("satir_net_tutar", "sum"))
    tekrar = g[g.siparis >= 2]
    risk = tekrar[tekrar.son < b.bit - pd.Timedelta(days=ESIK["kayip_gun"])]
    if len(risk) < ESIK["kayip_min"]:
        return []
    return [Tavsiye(
        "kayip_musteri", "kayip_musteri", "musteri",
        f"{sayi(len(risk))} sadık müşteri {ESIK['kayip_gun']} gündür alışveriş yapmadı",
        f"En az iki kez sipariş veren {sayi(len(tekrar))} müşterinin {sayi(len(risk))} kadarı son "
        f"{ESIK['kayip_gun']} günde gelmedi; geçmiş harcamaları toplam {tl(risk.ciro.sum())}.",
        "Mağaza takipçilerine özel kupon tanımlayın ve yeni ürünleri duyurun (Trendyol takipçi kuponu).",
        {"kaynak": ["siparisler"], "risk_musteri": int(len(risk)), "tekrar_eden": int(len(tekrar)),
         "risk_ciro": float(risk.ciro.sum())},
        "dusuk", "Müşteri geçmişi kısa (gerçek veride 3 ay); kimlikler anonim, yalnızca segment düzeyinde aksiyon.",
        "orta", None, "Etkisi TL ile ölçülmedi.")]


KURALLAR = [stok_tukenme, kalip_uyarisi, beden_onerici, yuksek_iade_riski, zarar_eden_urun, iade_artisi,
            sikayetli_urun, marji_yiyen_indirim, kampanya_firsati, geciken_cevap, kargo_desisi, capraz_satis,
            sezon_hazirligi, kayip_musteri]
