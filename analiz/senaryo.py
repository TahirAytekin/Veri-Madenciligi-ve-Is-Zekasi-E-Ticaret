"""Senaryo simülatörü (F1-05): "şunu değiştirirsem katkı payım ne olur?" sorusunu cevaplar.

    python -m analiz.senaryo --veri gercek --beden-iade-azalis 0.5
    python -m analiz.senaryo --veri gercek --ek-indirim 0.10 --esneklik 1.5

    from analiz.senaryo import simule
    sonuc = simule("gercek", beden_iade_azalis=0.5)
    sonuc["fark"]["katki_payi"], sonuc["aylik_katki_farki"], sonuc["ozet"]

Tahmin modeli değildir: seçilen dönemin gerçek değerlerinden (analiz/metrikler.py) birim başı bir kâr modeli kurar,
istenen kalemi değiştirip yeniden hesaplar. Varsayımlar sonuçla birlikte döner ve ekranda gösterilmelidir.

Birim başı model (A = satılan adet):
    elde kalan satış = A × (1 − iade oranı) × birim net fiyat
    komisyon         = elde kalan satış × komisyon oranı
    kargo + platform = A × (birim kargo + birim platform)          (paket sayısı adetle orantılı varsayılır)
    iade kargosu     = A × iade oranı × iade başı kargo
    katkı payı       = elde kalan satış − komisyon − kargo − platform − iade kargosu
"""
import argparse
import math

import numpy as np
import pandas as pd

from analiz import metrikler as m

VARSAYILAN_GUN = 90
TARIFE_GUN = 60           # desi senaryosu: güncel kargo tarifesi bu kadar günün faturalarından çıkarılır


# ====================================================
# 1) BAŞLANGIÇ DEĞERLERİ
# ====================================================

def donem(veri, baslangic=None, bitis=None):
    bit = pd.Timestamp(bitis).normalize() if bitis is not None else m.veri_araligi(veri)[1]
    bas = pd.Timestamp(baslangic).normalize() if baslangic is not None else bit - pd.Timedelta(days=VARSAYILAN_GUN - 1)
    return bas, bit


def _eksikse(deger, yedek):
    return yedek() if deger is None or math.isnan(deger) else deger


def baz_degerler(veri="sahte", baslangic=None, bitis=None):
    """Dönemin birim başı değerleri. İade oranı olgunlaşmış satırlardan (metrikler.iade_orani)."""
    bas, bit = donem(veri, baslangic, bitis)
    d = m.cerceveler(veri)["satis"]
    d = d[(d.siparis_tarihi >= bas) & (d.siparis_tarihi < bit + pd.Timedelta(days=1))]
    g = d[~d.iptal]
    adet = float(g.adet.sum())
    if adet == 0:
        raise ValueError(f"{bas.date()} – {bit.date()} arasında satış yok")
    kalan_net = float((g.kalan_adet * g.birim_net_fiyat).sum())
    # Dönemde yeterli olgun satır yoksa (ör. son 3 hafta) oranlar tüm veriden alınır
    iade_orani = _eksikse(m.hesapla("iade_orani", veri, bas, bit), lambda: m.hesapla("iade_orani", veri))
    beden_payi = _eksikse(m.hesapla("beden_kaynakli_iade_payi", veri, bas, bit),
                          lambda: m.hesapla("beden_kaynakli_iade_payi", veri))
    gozlenen_iade = float(d.iade_adet.sum())
    birim_kargo = float(g.kargo_payi.sum()) / adet
    return {
        "veri": veri, "baslangic": bas, "bitis": bit, "gun": (bit - bas).days + 1,
        "adet": adet,
        "birim_net_fiyat": float(g.satir_net_tutar.sum()) / adet,
        "iade_orani": float(iade_orani),
        "beden_payi": float(beden_payi),
        "komisyon_orani": float(g.komisyon_tutari.sum()) / kalan_net if kalan_net else 0.0,
        "birim_kargo": birim_kargo,
        "birim_platform": float(g.platform_payi.sum()) / adet,
        # İade başına kargo: gözlenen iade kargolarından; iade yoksa gönderi kargosunun 1,16 katı (gerçek veri oranı)
        "iade_basi_kargo": float(d.iade_kargo_payi.sum()) / gozlenen_iade if gozlenen_iade else birim_kargo * 1.16,
    }


def guncel_tarife(veri, bitis):
    """Son TARIFE_GUN günün faturalarından firma × desi medyan ücret. Tarife zamanla değiştiği için yalnızca güncel
    dönem kullanılır; desi azalınca ücret artamayacağından her firmada desiye göre azalmayan hale getirilir."""
    t = m.tablolar(veri)
    k = t["kargo_faturalari"]
    k = k[(k.gonderi_turu == "Gönderi Kargo Bedeli") & (k.fatura_tarihi <= bitis + pd.Timedelta(days=60))
          & (k.fatura_tarihi > bitis - pd.Timedelta(days=TARIFE_GUN))]
    k = k.merge(t["siparisler"][["paket_id", "kargo_firmasi"]], on="paket_id", how="left")
    k["kargo_firmasi"] = k.kargo_firmasi.fillna("bilinmiyor")
    tarife = (k.groupby(["kargo_firmasi", "desi"]).tutar.median().sort_index()
              .groupby(level=0).cummax())
    return k, tarife


def desi_orani(veri, desi_azalis, bitis):
    """Gönderilerin desisi `desi_azalis` kadar düşseydi kargo maliyeti hangi oranda değişirdi (yeni / eski).

    Eski ve yeni ücret aynı (güncel) tarifeyle hesaplanır; böylece yalnızca desinin etkisi ölçülür."""
    if desi_azalis == 0:
        return 1.0
    k, tarife = guncel_tarife(veri, bitis)
    if k.empty:
        return 1.0

    def ucret(firma, desi):
        firmalar = tarife.index.get_level_values(0)
        firma_tarife = tarife.loc[firma] if firma in firmalar else tarife.groupby(level=1).median()
        desiler = firma_tarife.index.values
        desi = max(int(desi), int(desiler.min()))
        return float(firma_tarife.iloc[np.argmin(np.abs(desiler - desi))])

    eski = sum(ucret(f, d) for f, d in zip(k.kargo_firmasi, k.desi))
    yeni = sum(ucret(f, d - desi_azalis) for f, d in zip(k.kargo_firmasi, k.desi))
    return float(yeni / eski) if eski else 1.0


# ====================================================
# 2) KÂR TABLOSU
# ====================================================

def kar_tablosu(adet, birim_net_fiyat, iade_orani, komisyon_orani, birim_kargo, birim_platform, iade_basi_kargo,
                maliyet_orani=None):
    satis = adet * birim_net_fiyat
    iade_adet = adet * iade_orani
    elde_kalan = satis * (1 - iade_orani)
    komisyon = elde_kalan * komisyon_orani
    kargo = adet * birim_kargo
    platform = adet * birim_platform
    iade_kargo = iade_adet * iade_basi_kargo
    katki = elde_kalan - komisyon - kargo - platform - iade_kargo
    t = {"satilan_adet": adet, "iade_adet": iade_adet, "net_satis": satis, "iade_tutari": satis - elde_kalan,
         "elde_kalan_satis": elde_kalan, "komisyon": komisyon, "kargo": kargo, "platform": platform,
         "iade_kargo": iade_kargo, "katki_payi": katki}
    if maliyet_orani is not None:
        # İade edilen ürün stoğa döner; maliyet yalnızca elde kalan birimler için
        t["urun_maliyeti"] = adet * (1 - iade_orani) * birim_net_fiyat * maliyet_orani
        t["net_kar"] = katki - t["urun_maliyeti"]
    return t


def _birim_katki(b, birim_net_fiyat):
    return ((1 - b["iade_orani"]) * birim_net_fiyat * (1 - b["komisyon_orani"]) - b["birim_kargo"]
            - b["birim_platform"] - b["iade_orani"] * b["iade_basi_kargo"])


# ====================================================
# 3) SENARYO
# ====================================================

def _kontrol(ad, deger, alt, ust):
    if not alt <= deger <= ust:
        raise ValueError(f"{ad} {alt} ile {ust} arasında olmalı (verilen: {deger})")


def simule(veri="sahte", baslangic=None, bitis=None, iade_azalis=0.0, beden_iade_azalis=0.0, ek_indirim=0.0,
           esneklik=None, komisyon_farki=0.0, desi_azalis=0, maliyet_orani=None):
    """Senaryoyu hesaplar.

    iade_azalis        tüm iadelerin göreli azalışı (0.2 = %20 daha az iade)
    beden_iade_azalis  yalnızca beden kaynaklı iadelerin göreli azalışı (0.5 = yarıya iner)
    ek_indirim         birim net fiyata ek indirim (0.10 = %10)
    esneklik           fiyat esnekliği; verilirse satış adedi (1 − ek_indirim)^(−esneklik) katına çıkar
    komisyon_farki     komisyon oranına eklenecek yüzde puan (−1 = 1 puan düşük)
    desi_azalis        gönderi başına desi azalışı (1 = her paket 1 desi küçük)
    maliyet_orani      ürün maliyeti / birim net fiyat (verilirse net kâr da hesaplanır)
    """
    _kontrol("iade_azalis", iade_azalis, 0, 1)
    _kontrol("beden_iade_azalis", beden_iade_azalis, 0, 1)
    _kontrol("ek_indirim", ek_indirim, 0, 0.9)
    _kontrol("komisyon_farki", komisyon_farki, -30, 30)
    _kontrol("desi_azalis", desi_azalis, 0, 10)
    if maliyet_orani is not None:
        _kontrol("maliyet_orani", maliyet_orani, 0, 1)
    if esneklik is not None:
        _kontrol("esneklik", esneklik, 0, 10)

    b = baz_degerler(veri, baslangic, bitis)
    ortak = dict(birim_platform=b["birim_platform"], iade_basi_kargo=b["iade_basi_kargo"], maliyet_orani=maliyet_orani)
    baz = kar_tablosu(b["adet"], b["birim_net_fiyat"], b["iade_orani"], b["komisyon_orani"], b["birim_kargo"], **ortak)

    iade = b["iade_orani"] * max(0.0, 1 - iade_azalis - b["beden_payi"] * beden_iade_azalis)
    fiyat = b["birim_net_fiyat"] * (1 - ek_indirim)
    adet = b["adet"] * ((1 - ek_indirim) ** -esneklik if esneklik is not None and ek_indirim else 1)
    komisyon = b["komisyon_orani"] + komisyon_farki / 100
    kargo = b["birim_kargo"] * desi_orani(veri, desi_azalis, b["bitis"])
    ortak["maliyet_orani"] = None if maliyet_orani is None else maliyet_orani / (1 - ek_indirim)  # maliyet TL sabit
    yeni = kar_tablosu(adet, fiyat, iade, komisyon, kargo, **ortak)

    fark = {k: yeni[k] - baz[k] for k in baz}
    sonuc = {
        "veri": veri,
        "donem": {"baslangic": str(b["baslangic"].date()), "bitis": str(b["bitis"].date()), "gun": b["gun"]},
        "parametreler": {"iade_azalis": iade_azalis, "beden_iade_azalis": beden_iade_azalis, "ek_indirim": ek_indirim,
                         "esneklik": esneklik, "komisyon_farki": komisyon_farki, "desi_azalis": desi_azalis,
                         "maliyet_orani": maliyet_orani},
        "baz_degerler": {k: (str(v.date()) if isinstance(v, pd.Timestamp) else v) for k, v in b.items()},
        "baz": baz, "senaryo": yeni, "fark": fark,
        "aylik_katki_farki": fark["katki_payi"] / b["gun"] * 30,
        "senaryo_iade_orani": iade,
        "varsayimlar": varsayimlar(ek_indirim, esneklik, desi_azalis, maliyet_orani),
    }
    if ek_indirim:
        sonuc["basa_bas"] = basa_bas(b, ek_indirim)
    sonuc["ozet"] = ozet_metni(sonuc)
    return sonuc


def basa_bas(b, ek_indirim):
    """İndirimin katkı payını düşürmemesi için satış adedinin kaç katına çıkması gerekir?"""
    once = _birim_katki(b, b["birim_net_fiyat"])
    sonra = _birim_katki(b, b["birim_net_fiyat"] * (1 - ek_indirim))
    if sonra <= 0:
        return {"carpan": None, "gerekli_artis": None, "birim_katki_once": once, "birim_katki_sonra": sonra,
                "aciklama": "Bu indirimle her satış zarar ettirir; satış ne kadar artarsa zarar o kadar büyür."}
    carpan = once / sonra
    esneklik = math.log(carpan) / -math.log(1 - ek_indirim)
    return {"carpan": carpan, "gerekli_artis": carpan - 1, "gerekli_esneklik": esneklik,
            "birim_katki_once": once, "birim_katki_sonra": sonra,
            "aciklama": f"Katkı payının düşmemesi için satış adedi en az %{(carpan - 1) * 100:.0f} artmalı "
                        f"(fiyat esnekliği en az {esneklik:.2f})."}


def varsayimlar(ek_indirim, esneklik, desi_azalis, maliyet_orani):
    v = ["İade oranı, teslimi üzerinden 21 gün geçmiş satırlardan hesaplanır.",
         "Önlenen iadelerde ürün müşteride kalır; satış ve komisyon buna göre artar, iade kargosu düşer.",
         "Kargo ve platform maliyeti satılan adetle orantılıdır.",
         "Komisyon, ortalama sepetteki karışım değişmeden kalır."]
    if ek_indirim:
        v.append("Satış adedi değişimi yalnızca verilen fiyat esnekliğinden gelir." if esneklik is not None else
                 "Fiyat esnekliği verilmediği için satış adedi değişmez; satış artışı için başa baş noktasına bakın.")
    if desi_azalis:
        v.append(f"Desi değişimi son {TARIFE_GUN} günün kargo firması × desi tarifesiyle hesaplanır; "
                 "Trendyol Express'te 0–2 desi aynı ücrettedir, tasarruf 3 desi ve üstünde başlar.")
    if maliyet_orani is not None:
        v.append("İade edilen ürün stoğa döner ve tekrar satılabilir; maliyet yalnızca elde kalan ürünler içindir.")
    return v


def ozet_metni(s):
    b, y, gun = s["baz"]["katki_payi"], s["senaryo"]["katki_payi"], s["donem"]["gun"]
    yon = "artar" if y > b else "azalır" if y < b else "değişmez"
    metin = (f"Bu senaryoda {gun} günlük katkı payı {_tl(b)} → {_tl(y)} olur ({yon}; fark {_tl(y - b, isaret=True)}, "
             f"aylık {_tl(s['aylik_katki_farki'], isaret=True)}).")
    if "basa_bas" in s:
        metin += " " + s["basa_bas"]["aciklama"]
    return metin


def _tl(x, isaret=False):
    on = "+" if isaret and x > 0 else ""
    return f"{on}{x:,.0f} TL".replace(",", ".")


# ====================================================
# 4) KOMUT SATIRI
# ====================================================

def _yazdir(s):
    print(f"Dönem: {s['donem']['baslangic']} – {s['donem']['bitis']} ({s['donem']['gun']} gün)\n")
    print(f"{'kalem':22s} {'bugün':>14s} {'senaryo':>14s} {'fark':>14s}")
    for k in s["baz"]:
        print(f"{k:22s} {s['baz'][k]:>14,.0f} {s['senaryo'][k]:>14,.0f} {s['fark'][k]:>+14,.0f}")
    print("\n" + s["ozet"] + "\n\nVarsayımlar:")
    for v in s["varsayimlar"]:
        print(f"  - {v}")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Ne olur senaryosu: katkı payı bugün ve senaryoda")
    p.add_argument("--veri", default="sahte", choices=["sahte", "gercek"])
    p.add_argument("--baslangic")
    p.add_argument("--bitis")
    p.add_argument("--iade-azalis", type=float, default=0.0, help="0.2 = tüm iadeler %%20 azalır")
    p.add_argument("--beden-iade-azalis", type=float, default=0.0, help="0.5 = beden kaynaklı iadeler yarıya iner")
    p.add_argument("--ek-indirim", type=float, default=0.0, help="0.1 = %%10 ek indirim")
    p.add_argument("--esneklik", type=float, help="fiyat esnekliği (ör. 1.5)")
    p.add_argument("--komisyon-farki", type=float, default=0.0, help="yüzde puan (−1 = 1 puan düşük)")
    p.add_argument("--desi-azalis", type=int, default=0)
    p.add_argument("--maliyet-orani", type=float, help="ürün maliyeti / net fiyat (ör. 0.4)")
    a = p.parse_args()
    _yazdir(simule(a.veri, a.baslangic, a.bitis, a.iade_azalis, a.beden_iade_azalis, a.ek_indirim, a.esneklik,
                   a.komisyon_farki, a.desi_azalis, a.maliyet_orani))
