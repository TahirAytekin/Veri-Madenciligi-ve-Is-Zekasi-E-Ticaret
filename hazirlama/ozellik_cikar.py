"""Temel tablolardan analiz / makine öğrenmesi için hazır tablolar üretir.

Kullanım:  python ozellik_cikar.py sahte                      (veya: gercek)
           python ozellik_cikar.py sahte --kesim 2026-06-30   (sızıntısız: yalnızca kesime kadar bilinenler)
Çıktı   :  veri/<klasor>/analiz/*.csv    (kesimle: veri/<klasor>/analiz_kesim_<tarih>/)

Kesimli çıktılar model ÖZELLİKLERİ içindir; hedefi kesimden sonraki dönemden kendiniz hesaplayın
(örnek: docs/MODEL_DOGRULAMA.md).

  satis_detay.csv            her satış satırı + sipariş + ürün bilgisi tek tabloda (keşifsel analiz)
  gunluk_satis.csv           mağaza geneli günlük seri + takvim özellikleri (satış tahmini)
  gunluk_urun_satis.csv      ürün (renk) x gün paneli, fiyat ve indirimle (talep tahmini, fiyat esnekliği)
  urun_ozet.csv              ürün başına performans, yorum ve soru özellikleri (ürün skorlama, öneri)
  musteri_ozet.csv           RFM ve davranış özellikleri (segmentasyon, CLV, churn)
  musteri_urun_etkilesim.csv müşteri x ürün satın alma matrisi (öneri sistemi / collaborative filtering)
  birlikte_alinanlar.csv     aynı pakette alınan model çiftleri, destek/güven/lift (çapraz satış)
  aylik_finans.csv           aylık kâr-zarar: satış, iade, komisyon, hakediş, kargo/reklam/platform giderleri
  beden_iade_analizi.csv     model x beden satış ve "küçük/büyük geldi" iade oranları (beden önerisi)

Katkı payı = elde kalan net satış - komisyon - kargo - iade kargo - platform bedeli (ÜRÜN MALİYETİ HARİÇ).
"""
import argparse
import sys

import numpy as np
import pandas as pd
from ortak import VERI, hepsini_oku, kesim_uygula, ozel_gunler

sys.stdout.reconfigure(encoding="utf-8")

p = argparse.ArgumentParser()
p.add_argument("klasor", nargs="?", default="sahte", choices=["sahte", "gercek"])
p.add_argument("--kesim", help="YYYY-AA-GG: yalnızca bu günün sonuna kadar bilinen veriyle hesapla")
args = p.parse_args()

KLASOR = VERI / args.klasor
CIKTI = KLASOR / (f"analiz_kesim_{args.kesim}" if args.kesim else "analiz")
CIKTI.mkdir(exist_ok=True)

t = hepsini_oku(KLASOR)
if args.kesim:
    t = kesim_uygula(t, args.kesim)
    print(f"Kesim: {args.kesim} (sonrası yok sayılıyor) -> {CIKTI.relative_to(VERI.parent).as_posix()}")
urunler, siparisler, satirlar = t["urunler"], t["siparisler"], t["siparis_satirlari"]
sorular, yorumlar = t["sorular"], t["urun_yorumlari"]
iadeler, finans, kesintiler, kargo = t["iadeler"], t["finans_hareketleri"], t["kesintiler"], t["kargo_faturalari"]

BUGUN = (pd.Timestamp(args.kesim) + pd.Timedelta(days=1, microseconds=-1) if args.kesim
         else siparisler.siparis_tarihi.max())

# Finans hareketlerinin işareti (satıcı açısından): + gelir, - geri alınan
ISARET = {"Satış": 1, "İndirim": -1, "Kupon": -1, "İade": -1, "İndirim İptal": 1, "Kupon İptal": 1,
          "ProvisionPositive": 1, "ProvisionNegative": -1, "ManualRefund": -1}
finans["isaret"] = finans.islem_turu.map(ISARET).fillna(0)
# Gider sayılmayanlar: Trendyol'un satıcıya ödemesi ve satır komisyonunun mükerrer haftalık faturası
GIDER = kesintiler[~kesintiler.grup.isin(["odeme", "komisyon_faturasi"])]
GIDER_GRUPLARI = ["kargo", "platform_hizmet", "reklam", "ceza_tazmin", "uluslararasi", "finansman", "diger"]
GIDER_SUTUNLARI = [f"gider_{g}" for g in GIDER_GRUPLARI]   # iki veri setinde de aynı sütunlar
kabul_iade = iadeler[iadeler.durum == "Accepted"]


def kaydet(df, ad):
    df.to_csv(CIKTI / f"{ad}.csv", index=False, encoding="utf-8-sig")
    print(f"  {ad}.csv: {len(df):,} satır, {df.shape[1]} sütun")


def takvim_ekle(df, sutun="tarih"):
    gunler = ozel_gunler(df[sutun].min().date(), df[sutun].max().date())
    d = df[sutun].dt
    df["yil"], df["ay"], df["hafta_gunu"] = d.year, d.month, d.dayofweek
    df["yilin_gunu"], df["ayin_gunu"] = d.dayofyear, d.day
    df["hafta_sonu"] = d.dayofweek >= 5
    df["maas_donemi"] = d.day.isin([1, 2, 15, 16])
    df["ozel_gun"] = df[sutun].dt.date.map(lambda x: gunler.get(x, ("",))[0])
    return df


# ====================================================
# 1) SATIŞ DETAY (tek geniş tablo)
# ====================================================

detay = (satirlar
         .merge(siparisler[["paket_id", "siparis_no", "musteri_id", "siparis_tarihi", "sehir", "odeme_yontemi",
                            "kargo_firmasi", "hizli_teslimat", "paket_durumu", "kargoya_verilis_tarihi",
                            "teslim_tarihi", "iptal"]], on="paket_id")
         .merge(urunler[["barkod", "icerik_id", "model_kodu", "urun_adi", "kategori"]], on="barkod", how="left"))
# Bölünmüş paketin ("UnPacked") satırları yeni paketlerde tekrar yer alır; çift sayılmasın
detay = detay[detay.paket_durumu != "UnPacked"]
detay["tarih"] = detay.siparis_tarihi.dt.normalize()
detay["saat"] = detay.siparis_tarihi.dt.hour
detay["indirim_orani"] = (1 - detay.birim_net_fiyat / detay.birim_brut_fiyat).round(4)
detay["komisyon_tutari"] = (detay.satir_net_tutar * detay.komisyon_orani / 100).round(2)
detay["kargo_suresi_saat"] = ((detay.kargoya_verilis_tarihi - detay.siparis_tarihi).dt.total_seconds() / 3600).round(1)
detay["teslim_suresi_saat"] = ((detay.teslim_tarihi - detay.siparis_tarihi).dt.total_seconds() / 3600).round(1)

# --- İadeler (satır bazında)
satir_iade = (iadeler[iadeler.durum != "Cancelled"].groupby("satir_id")
              .agg(iade_talep_adet=("iade_kalem_id", "size"), iade_neden_grubu=("neden_grubu", lambda s: s.mode().iat[0])))
detay = detay.join(satir_iade, on="satir_id")
detay = detay.join(kabul_iade.groupby("satir_id").size().rename("iade_kabul_adet"), on="satir_id")
detay[["iade_talep_adet", "iade_kabul_adet"]] = detay[["iade_talep_adet", "iade_kabul_adet"]].fillna(0).astype(int)

# --- Kargo maliyeti: paketin gönderi bedeli satırlara brüt tutara göre dağıtılır.
# Faturası henüz kesilmemiş (son ~4-6 hafta) paketlerde son 90 günün paket başı ortalaması kullanılır.
gonderi = kargo[kargo.gonderi_turu == "Gönderi Kargo Bedeli"].groupby("paket_id").tutar.sum()
iade_kargo = kargo[kargo.gonderi_turu == "İade Kargo Bedeli"].groupby("paket_id").tutar.sum()
son_kargo = kargo[(kargo.gonderi_turu == "Gönderi Kargo Bedeli") & (kargo.fatura_tarihi > kargo.fatura_tarihi.max() - pd.Timedelta(days=90))]
ort_kargo = son_kargo.tutar.mean() if len(son_kargo) else np.nan
pay = detay.birim_brut_fiyat * detay.adet / detay.groupby("paket_id").birim_brut_fiyat.transform(
    lambda s: (s * detay.loc[s.index, "adet"]).sum())
gonderildi = detay.kargoya_verilis_tarihi.notna()
detay["kargo_tahmini"] = gonderildi & ~detay.paket_id.isin(gonderi.index)
detay["kargo_payi"] = (detay.paket_id.map(gonderi).fillna(ort_kargo).where(gonderildi, 0) * pay).round(2)
iade_payi = detay.iade_kabul_adet * detay.birim_brut_fiyat
detay["iade_kargo_payi"] = (detay.paket_id.map(iade_kargo).fillna(0)
                            * iade_payi / iade_payi.groupby(detay.paket_id).transform("sum").replace(0, np.nan)).fillna(0).round(2)

# Platform hizmet bedeli: son 90 günde gönderi başına ortalama
son90 = GIDER[(GIDER.grup == "platform_hizmet") & (GIDER.islem_tarihi > GIDER.islem_tarihi.max() - pd.Timedelta(days=90))]
platform_paket = son90.borc.sum() / max(len(son_kargo), 1)
detay["platform_payi"] = (platform_paket * pay).where(gonderildi, 0).round(2)

# --- Katkı payı (ÜRÜN MALİYETİ HARİÇ): elde kalan net satış - komisyon - kargo - iade kargo - platform
kalan_adet = (detay.adet - detay.iade_kabul_adet).clip(lower=0).where(~detay.iptal, 0)
detay["katki_payi"] = (kalan_adet * detay.birim_net_fiyat * (1 - detay.komisyon_orani / 100)
                       - detay.kargo_payi - detay.iade_kargo_payi - detay.platform_payi).round(2)

detay = takvim_ekle(detay)
kaydet(detay, "satis_detay")

gecerli = detay[~detay.iptal]   # iptal edilenler ciroya katılmaz

# ====================================================
# 2) GÜNLÜK MAĞAZA SERİSİ
# ====================================================

ilk_siparis = siparisler.groupby("musteri_id").siparis_tarihi.min().dt.normalize()
sp = siparisler.assign(tarih=siparisler.siparis_tarihi.dt.normalize())
sp["yeni_musteri"] = sp.tarih.eq(sp.musteri_id.map(ilk_siparis))

gunluk = pd.DataFrame({"tarih": pd.date_range(sp.tarih.min(), sp.tarih.max())})
gunluk = (gunluk
          .merge(sp.groupby("tarih").agg(paket_sayisi=("paket_id", "size"),
                                         iptal_sayisi=("iptal", "sum"),
                                         yeni_musteri=("yeni_musteri", "sum")).reset_index(), how="left")
          .merge(gecerli.groupby("tarih").agg(satilan_adet=("adet", "sum"),
                                              ciro_net=("satir_net_tutar", "sum"),
                                              ciro_brut=("birim_brut_fiyat", lambda s: (s * gecerli.loc[s.index, "adet"]).sum()),
                                              komisyon=("komisyon_tutari", "sum")).reset_index(), how="left")
          .merge(sorular.assign(tarih=sorular.soru_tarihi.dt.normalize()).groupby("tarih").size()
                 .rename("soru_sayisi").reset_index(), how="left")
          .merge(yorumlar.assign(tarih=yorumlar.yorum_tarihi.dt.normalize()).groupby("tarih")
                 .agg(yorum_sayisi=("puan", "size"), ort_puan=("puan", "mean")).reset_index(), how="left"))
acik_iade = iadeler[iadeler.durum != "Cancelled"]
gunluk = gunluk.merge(
    acik_iade.assign(tarih=acik_iade.iade_tarihi.dt.normalize()).groupby("tarih")
    .agg(iade_talebi=("iade_kalem_id", "size"),
         beden_iadesi=("neden_grubu", lambda s: s.isin(["beden_kucuk", "beden_buyuk"]).sum())).reset_index(),
    how="left")
# Giderler işlem (fatura) tarihine göre: gider_reklam, gider_kargo, gider_platform_hizmet, gider_ceza_tazmin ...
gider_g = (GIDER.assign(tarih=GIDER.islem_tarihi.dt.normalize())
           .pivot_table(index="tarih", columns="grup", values="borc", aggfunc="sum").add_prefix("gider_")
           .reindex(columns=GIDER_SUTUNLARI).reset_index())
gunluk = gunluk.merge(gider_g, how="left")
gunluk = gunluk.fillna({c: 0 for c in gunluk.columns if c not in ("tarih", "ort_puan")})
gunluk["tekrar_musteri"] = gunluk.paket_sayisi - gunluk.yeni_musteri
gunluk["indirim_orani"] = (1 - gunluk.ciro_net / gunluk.ciro_brut).round(4)
gunluk["ort_sepet"] = (gunluk.ciro_net / (gunluk.paket_sayisi - gunluk.iptal_sayisi)).round(2)
gunluk = takvim_ekle(gunluk).round(2)
kaydet(gunluk, "gunluk_satis")

# ====================================================
# 3) ÜRÜN x GÜN PANELİ
# ====================================================

icerik = (urunler.dropna(subset=["icerik_id"])
          .groupby("icerik_id")
          .agg(model_kodu=("model_kodu", "first"), kategori=("kategori", "first"),
               olusturma=("olusturma_tarihi", "min"))
          .reset_index())
satis_g = (gecerli.dropna(subset=["icerik_id"])
           .groupby(["icerik_id", "tarih"])
           .agg(adet=("adet", "sum"), ciro_net=("satir_net_tutar", "sum"),
                ort_brut_fiyat=("birim_brut_fiyat", "mean"), ort_net_fiyat=("birim_net_fiyat", "mean"))
           .reset_index())
# Panel: ürünün eklendiği (ya da ilk sattığı) günden bugüne
baslangic = satis_g.groupby("icerik_id").tarih.min()
icerik["bas"] = icerik[["olusturma"]].assign(s=icerik.icerik_id.map(baslangic)).min(axis=1).dt.normalize()
icerik["bas"] = icerik.bas.clip(lower=detay.tarih.min())
icerik = icerik.dropna(subset=["bas"])
panel = pd.concat([pd.DataFrame({"icerik_id": r.icerik_id, "tarih": pd.date_range(r.bas, BUGUN.normalize())})
                   for r in icerik.itertuples()], ignore_index=True)
panel = (panel.merge(icerik[["icerik_id", "model_kodu", "kategori"]], on="icerik_id")
         .merge(satis_g, on=["icerik_id", "tarih"], how="left"))
panel[["adet", "ciro_net"]] = panel[["adet", "ciro_net"]].fillna(0)
# Satış olmayan günlerde fiyat: modelin son bilinen fiyatı
model_fiyat = (gecerli.groupby(["model_kodu", "tarih"]).birim_brut_fiyat.median().rename("model_fiyati").reset_index())
panel = panel.merge(model_fiyat, on=["model_kodu", "tarih"], how="left").sort_values(["icerik_id", "tarih"])
panel["fiyat"] = panel.groupby("icerik_id").model_fiyati.ffill()
panel = panel.drop(columns="model_fiyati")
panel["indirim_orani"] = (1 - panel.ort_net_fiyat / panel.ort_brut_fiyat).round(4)
panel = takvim_ekle(panel).round(2)
kaydet(panel, "gunluk_urun_satis")

# ====================================================
# 4) ÜRÜN ÖZETİ (renk / ürün sayfası düzeyinde)
# ====================================================

ozet = (urunler.dropna(subset=["icerik_id"]).groupby("icerik_id")
        .agg(model_kodu=("model_kodu", "first"), urun_adi=("urun_adi", "first"), kategori=("kategori", "first"),
             renk=("renk", "first"), varyant_sayisi=("barkod", "size"),
             stoklu_beden_orani=("stok", lambda s: (s > 0).mean()), toplam_stok=("stok", "sum"),
             satis_fiyati=("satis_fiyati", "median"), liste_fiyati=("liste_fiyati", "median"),
             satista=("satista", "any"), arsivde=("arsivde", "all"), olusturma=("olusturma_tarihi", "min"))
        .reset_index())
ozet["yas_gun"] = (BUGUN - ozet.olusturma).dt.days
ozet["kategori_fiyat_endeksi"] = (ozet.satis_fiyati / ozet.groupby("kategori").satis_fiyati.transform("median")).round(3)


def pencere(gun_bas, gun_bit, ad):
    s = gecerli[(gecerli.tarih > BUGUN - pd.Timedelta(days=gun_bas)) & (gecerli.tarih <= BUGUN - pd.Timedelta(days=gun_bit))]
    return s.groupby("icerik_id").adet.sum().rename(ad)


tum = detay.dropna(subset=["icerik_id"])
satis = tum.groupby("icerik_id").agg(
    ilk_satis=("tarih", "min"), son_satis=("tarih", "max"),
    toplam_adet=("adet", lambda s: s[~tum.loc[s.index, "iptal"]].sum()),
    toplam_ciro=("satir_net_tutar", lambda s: s[~tum.loc[s.index, "iptal"]].sum()),
    iptal_orani=("iptal", "mean"), ort_indirim_orani=("indirim_orani", "mean"),
    musteri_sayisi=("musteri_id", "nunique"))
yorum = yorumlar.groupby("icerik_id").agg(
    yorum_sayisi=("puan", "size"), ort_puan=("puan", "mean"),
    olumsuz_yorum_orani=("puan", lambda s: (s <= 2).mean()),
    dar_diyen_orani=("yorum", lambda s: s.str.contains(r"\bdar\b|küçük|kucuk|büyük al|buyuk al", case=False, na=False).mean()),
    bol_diyen_orani=("yorum", lambda s: s.str.contains(r"\bbol\b|küçük al|kucuk al|uzun geldi", case=False, na=False).mean()),
    fotografli_yorum=("fotografli", "sum"))
soru = sorular.groupby("model_kodu").agg(
    model_soru_sayisi=("soru_id", "size"), beden_soru_orani=("konu", lambda s: (s == "beden").mean()),
    ort_cevap_dk=("cevap_suresi_dk", "mean"))

# İade ve katkı (sipariş penceresindeki satışlar üzerinden)
katki = tum.groupby("icerik_id").agg(
    teslim_adet=("adet", lambda s: s[tum.loc[s.index, "teslim_tarihi"].notna()].sum()),
    iade_kabul_adet=("iade_kabul_adet", "sum"), toplam_katki=("katki_payi", "sum"))
neden = (tum[tum.iade_kabul_adet > 0].groupby(["icerik_id", "iade_neden_grubu"]).iade_kabul_adet.sum()
         .unstack(fill_value=0).reindex(columns=["beden_kucuk", "beden_buyuk", "begenmedim", "kusurlu",
                                                  "yanlis_eksik_urun"], fill_value=0))
katki = katki.join(neden).fillna(0)
for grup in neden.columns:
    katki[f"iade_{grup}_orani"] = (katki[grup] / katki.teslim_adet.replace(0, np.nan)).round(4)
katki["iade_orani"] = (katki.iade_kabul_adet / katki.teslim_adet.replace(0, np.nan)).round(4)
katki["birim_katki"] = (katki.toplam_katki / (katki.teslim_adet - katki.iade_kabul_adet).replace(0, np.nan)).round(2)
katki = katki.drop(columns=list(neden.columns))

# Finans kayıtlarından son 365 gün (gerçek veride sipariş API'sinin 3 ay sınırını aşar)
barkod_icerik = urunler.dropna(subset=["icerik_id"]).set_index("barkod").icerik_id
yil = finans[finans.islem_tarihi > BUGUN - pd.Timedelta(days=365)].assign(icerik_id=lambda x: x.barkod.map(barkod_icerik))
yillik = yil.groupby("icerik_id").agg(
    yil_satis_adet=("islem_turu", lambda s: (s == "Satış").sum()),
    yil_iade_adet=("islem_turu", lambda s: (s == "İade").sum()),
    yil_net_hakedis=("satici_hakedisi", lambda s: (s * yil.loc[s.index, "isaret"]).sum()))
yillik["yil_iade_orani"] = (yillik.yil_iade_adet / yillik.yil_satis_adet.replace(0, np.nan)).round(4)

ozet = (ozet.join(satis, on="icerik_id").join(pencere(30, 0, "son30_adet"), on="icerik_id")
        .join(pencere(90, 0, "son90_adet"), on="icerik_id").join(pencere(180, 90, "onceki90_adet"), on="icerik_id")
        .join(yorum, on="icerik_id").join(soru, on="model_kodu").join(katki, on="icerik_id").join(yillik, on="icerik_id"))
for s in ["toplam_adet", "toplam_ciro", "son30_adet", "son90_adet", "onceki90_adet", "yorum_sayisi",
          "fotografli_yorum", "model_soru_sayisi", "musteri_sayisi", "teslim_adet", "iade_kabul_adet",
          "toplam_katki", "yil_satis_adet", "yil_iade_adet", "yil_net_hakedis"]:
    ozet[s] = ozet[s].fillna(0)
ozet["gunluk_satis_hizi"] = (ozet.toplam_adet / ozet.yas_gun.clip(lower=1)
                             .where(ozet.olusturma.notna(), (BUGUN - ozet.ilk_satis).dt.days.clip(lower=1))).round(4)
ozet["trend_orani"] = ((ozet.son90_adet + 1) / (ozet.onceki90_adet + 1)).round(3)
kaydet(ozet.round(4), "urun_ozet")

# ====================================================
# 5) MÜŞTERİ ÖZETİ (RFM)
# ====================================================

musteri = gecerli.groupby("musteri_id").agg(
    sehir=("sehir", "last"), ilk_siparis=("siparis_tarihi", "min"), son_siparis=("siparis_tarihi", "max"),
    siparis_sayisi=("paket_id", "nunique"), toplam_adet=("adet", "sum"), toplam_harcama=("satir_net_tutar", "sum"),
    farkli_kategori=("kategori", "nunique"), ort_indirim_orani=("indirim_orani", "mean"),
    favori_kategori=("kategori", lambda s: s.mode().iat[0] if s.notna().any() else None))
musteri["ort_sepet"] = (musteri.toplam_harcama / musteri.siparis_sayisi).round(2)
musteri["recency_gun"] = (BUGUN - musteri.son_siparis).dt.days
musteri["musteri_yasi_gun"] = (BUGUN - musteri.ilk_siparis).dt.days
iptal = siparisler.groupby("musteri_id").iptal.sum().rename("iptal_sayisi")
musteri = musteri.join(iptal)
musteri = musteri.join(gecerli.groupby("musteri_id").iade_kabul_adet.sum().rename("iade_adet"))
musteri["iade_orani"] = (musteri.iade_adet / musteri.toplam_adet).round(4)
musteri["toplam_katki"] = gecerli.groupby("musteri_id").katki_payi.sum().round(2)


def puanla(s, ters=False):
    """1-5 arası çeyreklik puan (eşit değerler için sıralama kullanılır)."""
    p = pd.qcut(s.rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
    return 6 - p if ters else p


musteri["R"] = puanla(musteri.recency_gun, ters=True)
musteri["F"] = np.select([musteri.siparis_sayisi >= 3, musteri.siparis_sayisi == 2], [5, 3], 1)
musteri["M"] = puanla(musteri.toplam_harcama)
musteri["segment"] = np.select(
    [(musteri.F >= 3) & (musteri.R >= 4), musteri.F >= 3, (musteri.R >= 4) & (musteri.M >= 4), musteri.R >= 4,
     musteri.R <= 2],
    ["Sadık", "Risk Altında Sadık", "Yeni Değerli", "Yeni", "Kayıp"], "Uykuda")
kaydet(musteri.reset_index().round(4), "musteri_ozet")

# ====================================================
# 6) MÜŞTERİ x ÜRÜN ETKİLEŞİM
# ====================================================

etkilesim = (gecerli.dropna(subset=["icerik_id"])
             .groupby(["musteri_id", "icerik_id"])
             .agg(model_kodu=("model_kodu", "first"), kategori=("kategori", "first"), adet=("adet", "sum"),
                  toplam_tutar=("satir_net_tutar", "sum"), ilk_tarih=("siparis_tarihi", "min"),
                  son_tarih=("siparis_tarihi", "max"))
             .reset_index())
kaydet(etkilesim, "musteri_urun_etkilesim")

# ====================================================
# 7) BİRLİKTE ALINANLAR (model düzeyinde)
# ====================================================

sepet = gecerli.dropna(subset=["model_kodu"]).groupby("paket_id").model_kodu.unique()
toplam_sepet = len(sepet)
tekil = sepet.explode().value_counts()
ciftler = (pd.DataFrame([(a, b) for m in sepet if len(m) > 1 for i, a in enumerate(sorted(m)) for b in sorted(m)[i + 1:]],
                        columns=["model_a", "model_b"])
           .value_counts().rename("birlikte_sayi").reset_index())
if len(ciftler):
    model_kat = urunler.groupby("model_kodu").kategori.first()
    ciftler["kategori_a"] = ciftler.model_a.map(model_kat)
    ciftler["kategori_b"] = ciftler.model_b.map(model_kat)
    ciftler["a_sayi"] = ciftler.model_a.map(tekil)
    ciftler["b_sayi"] = ciftler.model_b.map(tekil)
    ciftler["destek"] = ciftler.birlikte_sayi / toplam_sepet
    ciftler["guven_a_b"] = ciftler.birlikte_sayi / ciftler.a_sayi
    ciftler["guven_b_a"] = ciftler.birlikte_sayi / ciftler.b_sayi
    ciftler["lift"] = ciftler.destek / ((ciftler.a_sayi / toplam_sepet) * (ciftler.b_sayi / toplam_sepet))
kaydet(ciftler.round(5), "birlikte_alinanlar")

# ====================================================
# 8) AYLIK FİNANS (kâr-zarar, ürün maliyeti hariç)
# ====================================================
# Finans hareketleri işlem (teslim/iade kabul) tarihine, giderler fatura tarihine göre aylanır.

f = finans.assign(ay=finans.islem_tarihi.dt.to_period("M").astype(str))
tutar = f.alacak + f.borc
aylik = f.groupby("ay").agg(
    satis_adet=("islem_turu", lambda s: (s == "Satış").sum()),
    iade_adet=("islem_turu", lambda s: (s == "İade").sum()),
    yurt_disi_satis_payi=("ulke", lambda s: (s[f.loc[s.index, "islem_turu"] == "Satış"] != "Türkiye").mean()))
for ad, turler in {"brut_satis": ["Satış"], "indirim": ["İndirim"], "kupon": ["Kupon"], "iade_tutari": ["İade"],
                   "indirim_kupon_iptali": ["İndirim İptal", "Kupon İptal"]}.items():
    aylik[ad] = tutar[f.islem_turu.isin(turler)].groupby(f.ay).sum()
aylik["net_komisyon"] = (f.komisyon_tutari * f.isaret).groupby(f.ay).sum()
aylik["net_hakedis"] = (f.satici_hakedisi * f.isaret).groupby(f.ay).sum()
giderler = GIDER.assign(ay=GIDER.islem_tarihi.dt.to_period("M").astype(str)).pivot_table(
    index="ay", columns="grup", values="borc", aggfunc="sum").add_prefix("gider_").reindex(columns=GIDER_SUTUNLARI)
aylik = aylik.join(giderler, how="outer").fillna(0)
aylik["toplam_gider"] = aylik[GIDER_SUTUNLARI].sum(axis=1)
aylik["net_kalan"] = aylik.net_hakedis - aylik.toplam_gider          # ürün maliyeti düşülmeden önce
aylik["iade_orani"] = (aylik.iade_adet / aylik.satis_adet.replace(0, np.nan)).round(4)
aylik["reklam_satis_orani"] = (aylik.get("gider_reklam", 0) / aylik.brut_satis.replace(0, np.nan)).round(4)
kaydet(aylik.reset_index().round(2), "aylik_finans")

# ====================================================
# 9) BEDEN İADE ANALİZİ (model x beden)
# ====================================================
# Satışlar finans kayıtlarından (gerçek veride 1 yıl), iadeler iade taleplerinden; ikisi de barkod ile ürüne bağlanır.
# kucuk_geldi_orani yüksekse: bu modelde bir beden büyük önerilmeli (ve tersi).

varyant = urunler.set_index("barkod")[["model_kodu", "kategori", "beden"]]
sat = finans[finans.islem_turu == "Satış"].join(varyant, on="barkod").dropna(subset=["model_kodu"])
# İadeler de satışlarla aynı döneme kısıtlanır (gerçek veride iadeler daha eskiye gider)
ia = (kabul_iade[kabul_iade.iade_tarihi >= finans.islem_tarihi.min() + pd.Timedelta(days=15)]
      .join(varyant, on="barkod", rsuffix="_urun").dropna(subset=["model_kodu"]))
beden = (sat.groupby(["model_kodu", "kategori", "beden"]).size().rename("satis_adet").to_frame()
         .join(ia.groupby(["model_kodu", "kategori", "beden"]).agg(
             iade_adet=("iade_kalem_id", "size"),
             kucuk_geldi=("neden_grubu", lambda s: (s == "beden_kucuk").sum()),
             buyuk_geldi=("neden_grubu", lambda s: (s == "beden_buyuk").sum())), how="left")
         .fillna(0).reset_index())
beden = beden[beden.satis_adet >= 5]
for s in ["iade_adet", "kucuk_geldi", "buyuk_geldi"]:
    beden[f"{s}_orani"] = (beden[s] / beden.satis_adet).round(4)
beden["kalip_egilimi"] = np.select(
    [beden.kucuk_geldi_orani - beden.buyuk_geldi_orani > 0.05, beden.buyuk_geldi_orani - beden.kucuk_geldi_orani > 0.05],
    ["dar", "bol"], "normal")
kaydet(beden, "beden_iade_analizi")
