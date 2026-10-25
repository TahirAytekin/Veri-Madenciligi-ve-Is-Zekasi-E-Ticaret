"""Durum analizi (F1-03): mağazanın bugünkü durumunu otomatik içgörülere ve bir sağlık skoruna çevirir.

    python -m analiz.durum --veri gercek        # -> ciktilar/gercek/durum_raporu.json ve .md

    from analiz.durum import durum_raporu
    rapor = durum_raporu("sahte")

Bütün sayılar analiz/metrikler.py üzerinden hesaplanır; bu modül yalnızca hangi sayının dikkat çektiğine karar verir ve
onu cümleye çevirir. Her içgörü kanıtını (metrik, değer, dönem) taşır; tavsiye motoru ve asistan "neden?" sorusunu
buradan cevaplar.
"""
import argparse
import json
import math
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from analiz import metrikler as m
from hazirlama.ortak import PROJE

CIKTILAR = PROJE / "ciktilar"
DONEM_GUN = 30          # "bugünkü durum" dönemi (önceki eşit dönemle karşılaştırılır)
YAPI_GUN = 90           # yapısal analizler (kategori, ürün, gün/saat, iade) için daha uzun dönem
GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
ONEM_SIRASI = {"yuksek": 0, "orta": 1, "dusuk": 2}


# ====================================================
# 1) İÇGÖRÜ VE BİÇİMLENDİRME
# ====================================================

@dataclass
class Icgoru:
    id: str
    alan: str                    # satis, urun, iade, karlilik, musteri, operasyon, musteri_sesi, stok
    baslik: str
    aciklama: str
    onem: str                    # yuksek, orta, dusuk
    yon: str                     # olumlu, olumsuz, notr
    kanit: dict
    ilgili: dict = field(default_factory=dict)   # {"kategori": [...], "model_kodu": [...]}


# Not: sayılardan sonra Türkçe ek ('i, 'sı ...) kullanılmaz; doğru ek sayının okunuşuna bağlıdır.
# Cümleler "pay %12", "oran %8" gibi eksiz kurulur.

def tl(x):
    return f"{x:,.0f} TL".replace(",", ".")


def yuzde(x, basamak=1):
    return f"%{x * 100:.{basamak}f}".replace(".", ",")


def sayi(x, basamak=0):
    return f"{x:,.{basamak}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _gecerli(x):
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def _degisim_cumlesi(degisim):
    if degisim >= 1:
        return f"{sayi(degisim + 1, 1)} katına çıktı"
    return f"{yuzde(abs(degisim))} {'arttı' if degisim > 0 else 'azaldı'}"


def _yon(degisim, iyi_yon):
    if not _gecerli(degisim) or iyi_yon == 0 or abs(degisim) < 0.05:
        return "notr"
    return "olumlu" if np.sign(degisim) == iyi_yon else "olumsuz"


class Baglam:
    """Bir rapor için ortak dönemler ve isim tabloları."""

    def __init__(self, veri):
        self.veri = veri
        self.veri_bas, self.bit = m.veri_araligi(veri)
        self.bas = self.bit - pd.Timedelta(days=DONEM_GUN - 1)
        self.ybas = max(self.bit - pd.Timedelta(days=YAPI_GUN - 1), self.veri_bas)
        u = m.tablolar(veri)["urunler"]
        self.model_adi = u.dropna(subset=["model_kodu"]).groupby("model_kodu").urun_adi.first().to_dict()

    def h(self, ad, uzun=False, **kw):
        return m.hesapla(ad, self.veri, self.ybas if uzun else self.bas, self.bit, **kw)

    def karsilastir(self, ad):
        return m.donem_karsilastir(ad, self.veri, self.bas, self.bit)

    def ad(self, model_kodu):
        return self.model_adi.get(model_kodu, model_kodu)

    def donem(self, uzun=False):
        return {"baslangic": str((self.ybas if uzun else self.bas).date()), "bitis": str(self.bit.date())}


# ====================================================
# 2) İÇGÖRÜ KURALLARI
# ====================================================
# Her kural bir Baglam alır ve 0 veya daha fazla Icgoru döndürür.

def satis_trendi(b):
    sonuc = []
    for ad, esik in [("ciro_net", 0.0), ("siparis_sayisi", 0.10), ("ortalama_sepet", 0.10)]:
        k = b.karsilastir(ad)
        metrik = m.METRIKLER[ad]
        bicim = tl if metrik.birim == "TL" else sayi
        if not _gecerli(k["degisim"]):
            if ad == "ciro_net":
                sonuc.append(Icgoru("satis_ciro", "satis", f"{metrik.baslik}: {bicim(k['deger'])}",
                                    f"Son {DONEM_GUN} günde {metrik.baslik.lower()} {bicim(k['deger'])}. "
                                    "Önceki dönem verisi olmadığı için karşılaştırma yapılamadı.",
                                    "orta", "notr", {"metrik": ad, "deger": k["deger"], **b.donem()}))
            continue
        if abs(k["degisim"]) < esik:
            continue
        onem = "yuksek" if abs(k["degisim"]) >= 0.25 else "orta"
        sonuc.append(Icgoru(
            f"satis_{ad}", "satis", f"{metrik.baslik} {_degisim_cumlesi(k['degisim'])}",
            f"Son {DONEM_GUN} günde {metrik.baslik.lower()} {bicim(k['deger'])}; önceki {DONEM_GUN} güne göre "
            f"{_degisim_cumlesi(k['degisim'])} (önceki: {bicim(k['onceki'])}).",
            onem, _yon(k["degisim"], metrik.iyi_yon),
            {"metrik": ad, "deger": k["deger"], "onceki": k["onceki"], "degisim": k["degisim"], **b.donem()}))
    return sonuc


def gun_ve_saat(b):
    paket = m.cerceveler(b.veri)["paket"]
    p = paket[(paket.siparis_tarihi >= b.ybas) & (paket.siparis_tarihi < b.bit + pd.Timedelta(days=1)) & ~paket.iptal]
    if len(p) < 100:
        return []
    gun_sayisi = pd.Series(pd.date_range(b.ybas, b.bit).dayofweek).value_counts()
    gunluk = (p.siparis_tarihi.dt.dayofweek.value_counts() / gun_sayisi).dropna()
    saat_payi = p.siparis_tarihi.dt.hour.value_counts(normalize=True).reindex(range(24), fill_value=0)
    pencere = pd.Series([saat_payi.iloc[[(h + i) % 24 for i in range(4)]].sum() for h in range(24)])
    en_iyi_saat = int(pencere.idxmax())
    en_iyi, en_kotu = int(gunluk.idxmax()), int(gunluk.idxmin())
    return [Icgoru(
        "zaman_yogunluk", "satis", f"En yoğun gün {GUNLER[en_iyi]}, en yoğun saatler {en_iyi_saat:02d}:00 sonrası",
        f"Son {YAPI_GUN} günde günlük ortalama sipariş en yüksek {GUNLER[en_iyi]} "
        f"({sayi(gunluk[en_iyi], 1)}), en düşük {GUNLER[en_kotu]} ({sayi(gunluk[en_kotu], 1)}). "
        f"{en_iyi_saat:02d}:00–{(en_iyi_saat + 4) % 24:02d}:00 arası verilen siparişlerin payı {yuzde(pencere.max())}.",
        "dusuk", "notr",
        {"metrik": "siparis_sayisi", "gunluk_ortalama": {GUNLER[i]: float(v) for i, v in gunluk.items()},
         "yogun_saat_baslangic": en_iyi_saat, "yogun_saat_payi": float(pencere.max()), **b.donem(uzun=True)})]


def pareto(b):
    ciro = b.h("ciro_net", uzun=True, kirilim="model_kodu")
    ciro = ciro[ciro > 0]
    if len(ciro) < 5:
        return []
    pay = ciro / ciro.sum()
    n80 = int((pay.cumsum() < 0.8).sum() + 1)
    ilk3 = pay.head(3)
    return [Icgoru(
        "urun_pareto", "urun", f"Cironun %80'i {n80} modelden geliyor ({len(ciro)} model içinde)",
        f"Son {YAPI_GUN} günde satış yapan {len(ciro)} model var; net satışın %80'ini bunlardan {n80} model "
        f"({yuzde(n80 / len(ciro), 0)}) oluşturuyor. İlk üç model: "
        + "; ".join(f"{b.ad(k)} ({yuzde(v)})" for k, v in ilk3.items()) + ".",
        "orta", "notr",
        {"metrik": "ciro_net", "model_sayisi": len(ciro), "yuzde80_model_sayisi": n80,
         "ilk3_pay": {k: float(v) for k, v in ilk3.items()}, **b.donem(uzun=True)},
        {"model_kodu": list(ilk3.index)})]


def kategori(b):
    simdi = b.h("ciro_net", kirilim="kategori")
    onceki = m.hesapla("ciro_net", b.veri, b.bas - pd.Timedelta(days=DONEM_GUN), b.bas - pd.Timedelta(days=1),
                       kirilim="kategori")
    if simdi.sum() <= 0:
        return []
    pay = simdi / simdi.sum()
    sonuc = [Icgoru(
        "kategori_payi", "urun", f"En çok satan kategori: {pay.index[0]} ({yuzde(pay.iloc[0])})",
        f"Son {DONEM_GUN} günde net satışta en büyük pay {pay.index[0]} ({yuzde(pay.iloc[0])}); ardından "
        f"{pay.index[1]} ({yuzde(pay.iloc[1])}) ve {pay.index[2]} ({yuzde(pay.iloc[2])}).",
        "dusuk", "notr", {"metrik": "ciro_net", "pay": {k: float(v) for k, v in pay.head(5).items()}, **b.donem()},
        {"kategori": list(pay.index[:3])})]
    if b.bas - pd.Timedelta(days=DONEM_GUN) >= b.veri_bas:
        degisim = ((simdi - onceki) / onceki).replace([np.inf, -np.inf], np.nan).dropna()
        onceki_pay = onceki / onceki.sum()
        # küçük tabandan hesaplanan büyüme abartılı görünür: iki dönemde de anlamlı payı olan kategoriler
        degisim = degisim[(pay.reindex(degisim.index) >= 0.05) & (onceki_pay.reindex(degisim.index) >= 0.03)]
        for k, v in [("buyuyen", degisim.max()), ("daralan", degisim.min())]:
            if not degisim.empty and abs(v) >= 0.20 and (v > 0) == (k == "buyuyen"):
                kat = degisim.idxmax() if k == "buyuyen" else degisim.idxmin()
                sonuc.append(Icgoru(
                    f"kategori_{k}", "urun", f"{kat} satışı {_degisim_cumlesi(v)}",
                    f"{kat} kategorisinin net satışı son {DONEM_GUN} günde {tl(simdi[kat])}; önceki döneme göre "
                    f"{_degisim_cumlesi(v)} (önceki: {tl(onceki[kat])}).",
                    "orta", "olumlu" if v > 0 else "olumsuz",
                    {"metrik": "ciro_net", "kategori": kat, "deger": float(simdi[kat]), "onceki": float(onceki[kat]),
                     "degisim": float(v), **b.donem()}, {"kategori": [kat]}))
    return sonuc


def iade(b):
    oran = b.h("iade_orani", uzun=True)
    beden = b.h("beden_kaynakli_iade_payi", uzun=True)
    if not _gecerli(oran):
        return []
    sonuc = [Icgoru(
        "iade_genel", "iade", f"İade oranı {yuzde(oran)}" + (f", beden kaynaklı iade payı {yuzde(beden, 0)}"
                                                              if _gecerli(beden) else ""),
        f"Son {YAPI_GUN} günün teslim edilmiş siparişlerinde (son {m.OLGUNLASMA_GUN} gün hariç) iade oranı "
        f"{yuzde(oran)}." + (f" 'Küçük geldi' veya 'büyük geldi' nedenli iadelerin payı {yuzde(beden, 0)}."
                             if _gecerli(beden) else ""),
        "yuksek" if oran >= 0.10 or (_gecerli(beden) and beden >= 0.5) else "orta",
        "olumsuz" if oran >= 0.10 else "notr",
        {"metrik": "iade_orani", "deger": oran, "beden_kaynakli_iade_payi": beden, **b.donem(uzun=True)})]

    kat = b.h("iade_orani", uzun=True, kirilim="kategori").dropna()
    yuksek = kat[kat >= oran * 1.5].head(3)
    if not yuksek.empty:
        sonuc.append(Icgoru(
            "iade_kategori", "iade", f"En çok iade edilen kategoriler: {', '.join(yuksek.index)}",
            "Ortalamanın 1,5 katından fazla iade edilen kategoriler: "
            + ", ".join(f"{k} ({yuzde(v)})" for k, v in yuksek.items()) + f". Mağaza ortalaması {yuzde(oran)}.",
            "yuksek", "olumsuz", {"metrik": "iade_orani", "kategori_oranlari": {k: float(v) for k, v in yuksek.items()},
                                  "ortalama": oran, **b.donem(uzun=True)}, {"kategori": list(yuksek.index)}))

    mod = b.h("iade_orani", uzun=True, kirilim="model_kodu").dropna()
    mod = mod[mod >= oran * 1.5].head(5)
    if not mod.empty:
        sonuc.append(Icgoru(
            "iade_model", "iade", f"{len(mod)} modelde iade oranı ortalamanın çok üstünde",
            "En yüksek iade oranlı modeller: " + "; ".join(f"{b.ad(k)} ({yuzde(v)})" for k, v in mod.items()) + ".",
            "yuksek", "olumsuz", {"metrik": "iade_orani", "model_oranlari": {k: float(v) for k, v in mod.items()},
                                  "ortalama": oran, **b.donem(uzun=True)}, {"model_kodu": list(mod.index)}))
    return sonuc


def karlilik(b):
    ciro = b.h("ciro_net")
    if ciro <= 0:
        return []
    marj = b.h("katki_marji")
    kalemler = {"komisyon": b.h("komisyon_tutari"), "kargo": b.h("kargo_gideri"),
                "iade kargo": b.h("iade_kargo_gideri"), "platform bedeli": b.h("platform_gideri")}
    paylar = {k: v / ciro for k, v in kalemler.items()}
    en_buyuk = max(paylar, key=paylar.get)
    sonuc = [Icgoru(
        "karlilik_marj", "karlilik", f"Katkı marjı {yuzde(marj, 0)} (ürün maliyeti öncesi)",
        f"Son {DONEM_GUN} günde net satış {tl(ciro)}, katkı payı {tl(b.h('katki_payi'))} ({yuzde(marj)}; ürün maliyeti "
        f"düşülmeden). En büyük kesinti {en_buyuk} ({yuzde(paylar[en_buyuk])}); "
        + ", ".join(f"{k} {yuzde(v)}" for k, v in paylar.items() if k != en_buyuk) + ".",
        "orta", "notr", {"metrik": "katki_marji", "deger": marj, "kesinti_paylari": paylar, **b.donem()})]

    katki = b.h("katki_payi", uzun=True, kirilim="model_kodu")
    zarar = katki[katki < 0].sort_values().head(5)
    if not zarar.empty:
        sonuc.append(Icgoru(
            "karlilik_zarar", "karlilik", f"{len(zarar)} model zarar ettiriyor (ürün maliyeti hariç bile)",
            f"Son {YAPI_GUN} günde katkı payı negatif olan modeller: "
            + "; ".join(f"{b.ad(k)} ({tl(v)})" for k, v in zarar.items())
            + ". İade, kargo ve komisyon bu ürünlerin satışını aşıyor.",
            "yuksek", "olumsuz", {"metrik": "katki_payi", "model_katkilari": {k: float(v) for k, v in zarar.items()},
                                  **b.donem(uzun=True)}, {"model_kodu": list(zarar.index)}))
    return sonuc


def indirim(b):
    k = b.karsilastir("indirim_orani")
    if not _gecerli(k["degisim"]) or abs(k["deger"] - k["onceki"]) < 0.02:
        return []
    return [Icgoru(
        "indirim_degisim", "satis", f"İndirim oranı {yuzde(k['onceki'])} → {yuzde(k['deger'])}",
        f"Son {DONEM_GUN} günde indirimlerin brüt ciroya oranı {yuzde(k['deger'])}; önceki dönemde "
        f"{yuzde(k['onceki'])} idi.", "orta", "olumsuz" if k["deger"] > k["onceki"] else "olumlu",
        {"metrik": "indirim_orani", "deger": k["deger"], "onceki": k["onceki"], **b.donem()})]


def musteri(b):
    tekrar = b.h("tekrar_eden_musteri_orani", uzun=True)
    il = b.h("siparis_sayisi", uzun=True, kirilim="sehir")
    pay = il / il.sum()
    return [Icgoru(
        "musteri_tekrar", "musteri", f"Tekrar alan müşteri oranı {yuzde(tekrar)}",
        f"Son {YAPI_GUN} günde sipariş veren müşteriler içinde birden fazla sipariş verenlerin oranı {yuzde(tekrar)}. "
        f"İlk üç ilin sipariş payı {yuzde(pay.head(3).sum(), 0)}: "
        + ", ".join(f"{k} ({yuzde(v)})" for k, v in pay.head(3).items()) + ".",
        "orta" if tekrar < 0.10 else "dusuk", "olumsuz" if tekrar < 0.10 else "notr",
        {"metrik": "tekrar_eden_musteri_orani", "deger": tekrar,
         "il_paylari": {k: float(v) for k, v in pay.head(5).items()}, **b.donem(uzun=True)},
        {"sehir": list(pay.index[:3])})]


def operasyon(b):
    kargo = b.h("kargoya_verilis_suresi_saat")
    teslim = b.h("teslim_suresi_saat")
    if not _gecerli(kargo):
        return []
    return [Icgoru(
        "operasyon_hiz", "operasyon", f"Siparişler ortalama {sayi(kargo)} saatte kargoya veriliyor",
        f"Son {DONEM_GUN} günde siparişten kargoya veriliş medyan {sayi(kargo, 1)} saat, siparişten teslime medyan "
        f"{sayi(teslim, 1)} saat.", "orta" if kargo > 24 else "dusuk", "olumsuz" if kargo > 24 else "olumlu",
        {"metrik": "kargoya_verilis_suresi_saat", "deger": kargo, "teslim_suresi_saat": teslim, **b.donem()})]


def musteri_sesi(b):
    sonuc = []
    puan = m.hesapla("ortalama_puan", b.veri)
    olumsuz = m.hesapla("olumsuz_yorum_orani", b.veri)
    sayisi = m.hesapla("yorum_sayisi", b.veri)
    if _gecerli(puan):
        sonuc.append(Icgoru(
            "yorum_puan", "musteri_sesi", f"Ortalama ürün puanı {sayi(puan, 2)}",
            f"{sayi(sayisi)} ürün yorumunun ortalaması {sayi(puan, 2)}; 1–2 puanlı yorumların oranı {yuzde(olumsuz)}.",
            "orta" if olumsuz >= 0.15 else "dusuk", "olumsuz" if olumsuz >= 0.15 else "notr",
            {"metrik": "ortalama_puan", "deger": puan, "olumsuz_yorum_orani": olumsuz, "yorum_sayisi": sayisi}))
        yorum = m.cerceveler(b.veri)["urun_yorum"]
        kat = yorum.groupby("kategori").puan.agg(["mean", "size"])
        dusuk = kat[(kat["size"] >= 5) & (kat["mean"] < 3.5)].sort_values("mean").head(3)
        if not dusuk.empty:
            sonuc.append(Icgoru(
                "yorum_dusuk_kategori", "musteri_sesi", f"Düşük puanlı kategoriler: {', '.join(dusuk.index)}",
                "En az 5 yorumu olan ve ortalaması 3,5'in altında kalan kategoriler: "
                + ", ".join(f"{k} ({sayi(r['mean'], 2)}, {int(r['size'])} yorum)" for k, r in dusuk.iterrows()) + ".",
                "orta", "olumsuz", {"metrik": "ortalama_puan", "kategori_puanlari": dusuk["mean"].to_dict()},
                {"kategori": list(dusuk.index)}))
    cevap = b.h("medyan_cevap_suresi_dk")
    beden = b.h("beden_sorusu_orani", uzun=True)
    if _gecerli(beden):
        sonuc.append(Icgoru(
            "soru_beden", "musteri_sesi", f"Beden sorularının payı {yuzde(beden, 0)}",
            f"Son {YAPI_GUN} günde {sayi(b.h('soru_sayisi', uzun=True))} soru geldi; beden ile ilgili olanların payı "
            f"{yuzde(beden, 0)}."
            + (f" Son {DONEM_GUN} günde medyan cevap süresi {sayi(cevap)} dakika." if _gecerli(cevap) else ""),
            "yuksek" if beden >= 0.5 else "orta", "olumsuz" if beden >= 0.5 else "notr",
            {"metrik": "beden_sorusu_orani", "deger": beden, "medyan_cevap_suresi_dk": cevap, **b.donem(uzun=True)}))
    return sonuc


def stok(b):
    """Son dönemde en çok satan varyantlardan bugün stokta olmayanlar (urunler bugünün durumudur)."""
    s = m.cerceveler(b.veri)["satis"]
    son = s[(s.siparis_tarihi >= b.bas) & ~s.iptal].groupby("barkod").adet.sum().sort_values(ascending=False).head(50)
    if son.empty:
        return []
    u = m.tablolar(b.veri)["urunler"].drop_duplicates("barkod").set_index("barkod")
    bitti = u.reindex(son.index)
    bitti = bitti[(bitti.stok <= 0) & bitti.katalogda.fillna(False).astype(bool)]
    if bitti.empty:
        return []
    modeller = bitti.model_kodu.dropna().unique().tolist()
    return [Icgoru(
        "stok_tukenen", "stok", f"Çok satan {len(bitti)} varyant şu an stokta yok",
        f"Son {DONEM_GUN} günün en çok satan 50 varyantı içinde bugün stokta olmayan: {len(bitti)} (ör. "
        + "; ".join(f"{b.ad(r.model_kodu)} {r.beden}" for r in bitti.head(3).itertuples()) + ").",
        "yuksek" if len(bitti) >= 5 else "orta", "olumsuz",
        {"metrik": "satilan_adet", "tukenen_barkodlar": list(bitti.index), "incelenen": len(son), **b.donem()},
        {"model_kodu": modeller})]


KURALLAR = [satis_trendi, gun_ve_saat, pareto, kategori, iade, karlilik, indirim, musteri, operasyon, musteri_sesi,
            stok]


# ====================================================
# 3) SAĞLIK SKORU
# ====================================================
# Her bileşen 0–100 arası doğrusal ölçeklenir. Eşikler bu proje için seçilmiş kabullerdir (sektör ortalaması değil):
# "kötü" değerde 0, "iyi" değerde 100 puan.

SKOR_BILESENLERI = [
    # ad, başlık, metrik, uzun dönem mi, kötü değer, iyi değer
    ("buyume", "Büyüme", "ciro_net:degisim", False, -0.30, 0.30),
    ("iade", "İade", "iade_orani", True, 0.25, 0.05),
    ("karlilik", "Kârlılık", "katki_marji", False, 0.30, 0.70),
    ("memnuniyet", "Müşteri memnuniyeti", "ortalama_puan", True, 3.0, 4.8),
    ("kargo_hizi", "Kargo hızı", "kargoya_verilis_suresi_saat", False, 48, 12),
    ("musteri_hizmeti", "Müşteri hizmeti", "medyan_cevap_suresi_dk", False, 240, 15),
]


def saglik_skoru(b):
    bilesenler = []
    for ad, baslik, metrik, uzun, kotu, iyi in SKOR_BILESENLERI:
        if metrik.endswith(":degisim"):
            deger = b.karsilastir(metrik.split(":")[0])["degisim"]
        else:
            deger = b.h(metrik, uzun=uzun)
        puan = float(np.clip((deger - kotu) / (iyi - kotu) * 100, 0, 100)) if _gecerli(deger) else None
        bilesenler.append({"ad": ad, "baslik": baslik, "metrik": metrik, "deger": deger, "puan": puan,
                           "kotu": kotu, "iyi": iyi})
    puanlar = [x["puan"] for x in bilesenler if x["puan"] is not None]
    return {"skor": float(np.mean(puanlar)) if puanlar else None, "bilesenler": bilesenler}


# ====================================================
# 4) RAPOR
# ====================================================

def _json_uyumlu(x):
    if isinstance(x, dict):
        return {str(k): _json_uyumlu(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_json_uyumlu(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return None if math.isnan(x) else float(x)
    if isinstance(x, pd.Timestamp):
        return str(x.date())
    return x


def durum_raporu(veri="sahte"):
    """Mağazanın bugünkü durumu: dönem, sağlık skoru, ana KPI'lar ve önem sırasına dizilmiş içgörüler."""
    b = Baglam(veri)
    icgoruler = [i for kural in KURALLAR for i in kural(b)]
    icgoruler.sort(key=lambda i: (ONEM_SIRASI[i.onem], i.yon != "olumsuz"))
    kpi = m.ozet(veri, b.bas, b.bit)
    return _json_uyumlu({
        "veri": veri,
        "donem": b.donem(),
        "yapisal_donem": b.donem(uzun=True),
        "veri_araligi": {"baslangic": b.veri_bas, "bitis": b.bit},
        "saglik_skoru": saglik_skoru(b),
        "kpi": kpi.to_dict("records"),
        "icgoruler": [asdict(i) for i in icgoruler],
    })


def markdown(rapor):
    """Raporun okunabilir hali (asistan bilgi tabanı ve insan okuması için)."""
    s = rapor["saglik_skoru"]
    satirlar = [f"# Mağaza durum raporu ({rapor['veri']})", "",
                f"Dönem: {rapor['donem']['baslangic']} – {rapor['donem']['bitis']} · "
                f"Sağlık skoru: **{sayi(s['skor'])}/100**", "", "## Sağlık skoru bileşenleri", "",
                "| bileşen | değer | puan |", "|---|---|---|"]
    for x in s["bilesenler"]:
        satirlar.append(f"| {x['baslik']} | {'—' if x['deger'] is None else sayi(x['deger'], 3)} | "
                        f"{'—' if x['puan'] is None else sayi(x['puan'])} |")
    satirlar += ["", "## İçgörüler", ""]
    for i in rapor["icgoruler"]:
        isaret = {"olumlu": "▲", "olumsuz": "▼", "notr": "•"}[i["yon"]]
        satirlar.append(f"- {isaret} **{i['baslik']}** ({i['onem']}): {i['aciklama']}")
    return "\n".join(satirlar) + "\n"


def kaydet(veri):
    rapor = durum_raporu(veri)
    klasor = CIKTILAR / veri
    klasor.mkdir(parents=True, exist_ok=True)
    (klasor / "durum_raporu.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=2), encoding="utf-8")
    (klasor / "durum_raporu.md").write_text(markdown(rapor), encoding="utf-8")
    return rapor


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Durum raporu üretir: ciktilar/<veri>/durum_raporu.json ve .md")
    p.add_argument("--veri", default="sahte", choices=["sahte", "gercek"])
    args = p.parse_args()
    r = kaydet(args.veri)
    print(f"Sağlık skoru: {sayi(r['saglik_skoru']['skor'])}/100 · {len(r['icgoruler'])} içgörü "
          f"-> ciktilar/{args.veri}/durum_raporu.json")
