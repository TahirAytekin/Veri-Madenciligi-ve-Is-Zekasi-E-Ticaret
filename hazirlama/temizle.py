"""Ham Trendyol çıktılarını birbirine bağlanan, kişisel veriden arındırılmış tablolara çevirir.

Girdi : veri/ham/ (cekim/ betiklerinin çıktıları)
Çıktı : veri/gercek/*.csv   (GERÇEK VERİDİR - paylaşmayın)

Kişisel veriler (ad, adres, telefon, e-posta, TC ...) cekim/anonim.py ile daha ham dosyaya yazılmadan atılır;
müşteri ID'si ve kargo takip no orada özetlenir. Burada yalnızca analiz için gereken alanlar seçilir.
"""
import hashlib
import json
import sys

import pandas as pd
from ortak import HAM, TABLOLAR, VERI, env_degeri, iade_neden_grubu, indirim_turu, kaydet, kesinti_grubu, soru_konusu

sys.stdout.reconfigure(encoding="utf-8")

CIKTI = VERI / "gercek"
def _tuz():
    """Müşteri ID özetine eklenen tuz: yalnızca .env'den (kodda varsayılan değer yok; bkz. .github/kontrol.py)."""
    tuz = env_degeri("MUSTERI_ID_TUZ")
    if not tuz:
        raise SystemExit("MUSTERI_ID_TUZ .env dosyasında tanımlı olmalı (bkz. .env.example)")
    return tuz


def musteri_id(ham_id):
    """cekim/ betikleri ID'yi zaten özetleyerek yazar; eski ham dosyalar için burada özetlenir."""
    ham_id = str(ham_id)
    if ham_id.startswith("M") and len(ham_id) == 11:
        return ham_id
    return "M" + hashlib.sha256(f"{_tuz()}{ham_id}".encode()).hexdigest()[:10]


# Trendyol sipariş API'si orderDate'i Türkiye saatinde, diğer zamanları UTC olarak veriyor.
def tr_saati(ms):
    return pd.to_datetime(ms, unit="ms") + pd.Timedelta(hours=3) if ms else pd.NaT


def yerel_saat(ms):
    return pd.to_datetime(ms, unit="ms") if ms else pd.NaT


def tr_saati_seri(ms):
    return pd.to_datetime(ms, unit="ms") + pd.Timedelta(hours=3)


# ====================================================
# 1) SİPARİŞLER
# ====================================================

with open(HAM / "trendyol_tum_siparisler.json", encoding="utf-8") as f:
    ham_siparisler = json.load(f)

paketler, satirlar, gecmis, indirimler = [], [], [], []
# Finans ve iade kayıtlarını bağlamak için (çıktıya yazılmaz):
kalem_satir = {}   # birim kalem ID'si (orderLineItemId) -> satir_id
takip_paket = {}   # kargo takip no -> paket_id

for o in ham_siparisler:
    pid = o["shipmentPackageId"]
    if o.get("cargoTrackingNumber"):
        takip_paket[o["cargoTrackingNumber"]] = pid
    durumlar = {}
    for h in o.get("packageHistories") or []:
        t = tr_saati(h["createdDate"])
        gecmis.append({"paket_id": pid, "durum": h["status"], "tarih": t})
        durumlar.setdefault(h["status"], t)

    adres = o.get("shipmentAddress") or {}
    paketler.append({
        "paket_id": pid,
        "siparis_no": o["orderNumber"],
        "musteri_id": musteri_id(o["customerId"]),
        "siparis_tarihi": yerel_saat(o["orderDate"]),
        "sehir": adres.get("city"),
        "ilce": adres.get("district"),
        "odeme_yontemi": None if o.get("paymentMethod") in (None, "-") else o["paymentMethod"],
        "kargo_firmasi": (o.get("cargoProviderName") or "").replace(" Marketplace", ""),
        "hizli_teslimat": o.get("fastDeliveryType") or "Yok",
        "paket_durumu": o.get("shipmentPackageStatus") or o.get("status"),
        "brut_tutar": o.get("packageGrossAmount", o.get("grossAmount")),
        "satici_indirimi": o.get("packageSellerDiscount", 0),
        "trendyol_indirimi": o.get("packageTyDiscount", 0),
        "net_tutar": o.get("packageTotalPrice", o.get("totalPrice")),
        "tahmini_teslim_bas": tr_saati(o.get("estimatedDeliveryStartDate")),
        "tahmini_teslim_bit": tr_saati(o.get("estimatedDeliveryEndDate")),
        "kargoya_verilis_tarihi": durumlar.get("Shipped", pd.NaT),
        "teslim_tarihi": durumlar.get("Delivered", pd.NaT),
        "iptal": "Cancelled" in durumlar,
        "teslim_edilemedi": "UnDelivered" in durumlar,
        "iade_dondu": "Returned" in durumlar,
    })

    for x in o.get("discountDisplays") or []:
        indirimler.append({
            "paket_id": pid,
            "indirim_adi": x["displayName"],
            "indirim_turu": indirim_turu(x["displayName"]),
            "tutar": x["discountAmount"],
        })

    for ham_satir in o["lines"]:
        for kalem in ham_satir.get("discountDetails") or []:
            kalem_satir[int(kalem["lineItemId"])] = ham_satir["id"]
        satirlar.append({
            "satir_id": ham_satir["id"],
            "paket_id": pid,
            "barkod": ham_satir["barcode"],
            "urun_kodu": ham_satir["productCode"],
            "adet": ham_satir["quantity"],
            "beden": ham_satir.get("productSize"),
            "renk": ham_satir.get("productColor"),
            "birim_brut_fiyat": ham_satir["amount"],
            "birim_satici_indirimi": ham_satir.get("lineSellerDiscount", 0),
            "birim_trendyol_indirimi": ham_satir.get("lineTyDiscount", 0),
            "birim_net_fiyat": ham_satir["price"],
            "satir_net_tutar": round(ham_satir["price"] * ham_satir["quantity"], 2),
            "komisyon_orani": ham_satir.get("commission"),
            "kdv_orani": ham_satir.get("vatRate"),
            "is_birimi": ham_satir.get("businessUnit"),
            "satir_durumu": ham_satir.get("orderLineItemStatusName"),
            # yalnızca katalog dışı ürünleri tamamlamak için
            "_urun_adi": ham_satir.get("productName"),
            "_kategori_id": ham_satir.get("productCategoryId"),
        })

siparisler = pd.DataFrame(paketler)
satirlar = pd.DataFrame(satirlar)

# ====================================================
# 2) ÜRÜNLER
# ====================================================

ham = pd.read_csv(HAM / "trendyol_urunler.csv", encoding="utf-8-sig")
urunler = pd.DataFrame({
    "barkod": ham.barcode,
    "urun_kodu": ham.productCode,
    "icerik_id": ham.productContentId,
    "model_kodu": ham.productMainId,
    "urun_adi": ham.title,
    "kategori": ham.categoryName,
    "renk": ham.renk,
    "beden": ham.beden.astype("string"),
    # 0 TL fiyat = fiyat girilmemiş ürün
    "liste_fiyati": ham.listPrice.where(ham.listPrice > 0),
    "satis_fiyati": ham.salePrice.where(ham.salePrice > 0),
    "stok": ham.stok,
    "satista": ham.onSale,
    "arsivde": ham.archived,
    "katalogda": True,
    "olusturma_tarihi": pd.to_datetime(ham.createDateTime, unit="ms") + pd.Timedelta(hours=3),
})

# İş birimi ürün API'sinde yok; siparişlerden kategoriye göre alınır
eslesen = satirlar.merge(urunler[["barkod", "kategori"]], on="barkod")
kategori_is_birimi = eslesen.groupby("kategori").is_birimi.agg(lambda s: s.mode()[0])
urunler["is_birimi"] = urunler.kategori.map(kategori_is_birimi)

# Siparişte geçip katalogdan silinmiş varyantlar: siparişteki bilgilerle eklenir
kategori_adi = eslesen.groupby("_kategori_id").kategori.agg(lambda s: s.mode()[0])
silinen = (satirlar[~satirlar.barkod.isin(urunler.barkod)]
           .sort_values("satir_id").drop_duplicates("barkod", keep="last"))
urunler = pd.concat([urunler, pd.DataFrame({
    "barkod": silinen.barkod,
    "urun_kodu": silinen.urun_kodu,
    "urun_adi": silinen._urun_adi.str.replace(r",\s*[^,]*$", "", regex=True),
    "kategori": silinen._kategori_id.map(kategori_adi),
    "is_birimi": silinen.is_birimi,
    "renk": silinen.renk,
    "beden": silinen.beden,
    "stok": 0,
    "satista": False,
    "arsivde": True,
    "katalogda": False,
})], ignore_index=True)

# ====================================================
# 3) SORULAR VE YORUMLAR
# ====================================================

ham = pd.read_csv(HAM / "trendyol_sorular.csv", encoding="utf-8-sig")
sorular = pd.DataFrame({
    "soru_id": ham.soru_id,
    "model_kodu": ham.productMainId,
    "soru_tarihi": pd.to_datetime(ham.tarih),
    "soru": ham.soru,
    "konu": ham.soru.map(soru_konusu),
    "durum": ham.durum,
    "cevap": ham.cevap,
    "cevap_tarihi": pd.to_datetime(ham.cevap_tarihi),
})
sorular["cevap_suresi_dk"] = (sorular.cevap_tarihi - sorular.soru_tarihi).dt.total_seconds() / 60

ham = pd.read_csv(HAM / "trendyol_urun_yorumlari.csv", encoding="utf-8-sig")
urun_yorumlari = pd.DataFrame({
    "yorum_id": ham.yorum_id,
    "icerik_id": ham.contentId,
    "yorum_tarihi": pd.to_datetime(ham.tarih),
    "puan": ham.puan,
    "yorum": ham.yorum,
    "beden": ham.beden,
    "boy": ham.boy,
    "kilo": ham.kilo,
    "begeni": ham.begeni,
    "fotografli": ham.fotografli,
})

ham = pd.read_csv(HAM / "trendyol_satici_yorumlari.csv", encoding="utf-8-sig")
platform = ham.platform.str.lower().replace({"iphone": "ios", "mobilewebv2": "mweb"})
satici_yorumlari = pd.DataFrame({
    "yorum_id": ham.yorum_id,
    "yorum_tarihi": pd.to_datetime(ham.tarih),
    "satici_puani": ham.satici_puani,
    "kargo_puani": ham.kargo_puani,
    "yorum": ham.yorum,
    "satici_nedenleri": ham.satici_nedenleri,
    "kargo_nedenleri": ham.kargo_nedenleri,
    "platform": platform,
})

# ====================================================
# 4) İADELER (iadeler.py çıktısı)
# ====================================================
# Talepteki her ürün birimi bir satır. Yurt dışı (mikro ihracat) siparişlerin iadeleri de gelir;
# bunlar siparis_satirlari'na bağlanmaz ama barkod ile urunler'e bağlanır.

iade_satirlari = []
yol = HAM / "trendyol_iadeler.json"
if yol.exists():
    with open(yol, encoding="utf-8") as f:
        for c in json.load(f):
            for it in c.get("items") or []:
                ol = it["orderLine"]
                for ci in it.get("claimItems") or []:
                    neden = ci.get("customerClaimItemReason") or {}
                    iade_satirlari.append({
                        "iade_kalem_id": ci["id"],
                        "iade_id": c["id"],
                        "siparis_no": c["orderNumber"],
                        "paket_id": c.get("orderShipmentPackageId"),
                        "satir_id": ol["id"],
                        "kalem_id": ci.get("orderLineItemId"),
                        "barkod": ol.get("barcode"),
                        "siparis_tarihi": tr_saati(c.get("orderDate")),
                        "iade_tarihi": tr_saati(c.get("claimDate")),
                        "neden_kodu": neden.get("code"),
                        "neden": neden.get("name"),
                        "neden_grubu": iade_neden_grubu(neden.get("code")),
                        "musteri_notu": ci.get("customerNote") or None,
                        "durum": (ci.get("claimItemStatus") or {}).get("name"),
                        "karar_veren": ci.get("acceptDetail"),
                        "kargo_firmasi": (c.get("cargoProviderName") or "").replace(" Marketplace", ""),
                        "son_guncelleme": tr_saati(c.get("lastModifiedDate")),
                        "_urun_adi": ol.get("productName"),
                        "_renk": ol.get("productColor"),
                        "_beden": ol.get("productSize"),
                    })
else:
    print("UYARI: trendyol_iadeler.json yok, önce 'python -m cekim.iadeler' çalıştırın.")
iadeler = pd.DataFrame(iade_satirlari, columns=TABLOLAR["iadeler"] + ["_urun_adi", "_renk", "_beden"])

# İade kaydındaki paket no (orderShipmentPackageId) sipariş tablosundaki paket_id ile aynı kimlik değil.
# Paket, satır üzerinden bulunur; bölünmüş (UnPacked) ve iptal kopyalar yerine teslim edilen paket seçilir.
satir_paketi = (satirlar[["satir_id", "paket_id"]]
                .merge(siparisler[["paket_id", "paket_durumu"]], on="paket_id")
                .assign(kopya=lambda x: x.paket_durumu.isin(["UnPacked", "Cancelled"]))
                .sort_values("kopya").drop_duplicates("satir_id").set_index("satir_id").paket_id)
iadeler["paket_id"] = iadeler.satir_id.map(satir_paketi).astype("Int64")

# İadesi olup katalogda hiç olmayan eski varyantlar da ürün tablosuna eklenir
eksik = iadeler[~iadeler.barkod.isin(urunler.barkod)].drop_duplicates("barkod", keep="last")
urunler = pd.concat([urunler, pd.DataFrame({
    "barkod": eksik.barkod,
    "urun_adi": eksik._urun_adi.str.replace(r",\s*[^,]*$", "", regex=True),
    "renk": eksik._renk, "beden": eksik._beden,
    "stok": 0, "satista": False, "arsivde": True, "katalogda": False,
})], ignore_index=True)

# ====================================================
# 5) FİNANS (finans.py çıktısı)
# ====================================================
# Satış kaydı ürün TESLİM edildiğinde, birim (kalem) başına düşer.
#   satici_hakedisi toplamı = Satış - İndirim - Kupon - İade + İndirim İptal + Kupon İptal (hakediş sütunları)
# Bu API'nin tüm zaman damgaları UTC'dir.

finans_hareketleri = pd.DataFrame(columns=TABLOLAR["finans_hareketleri"])
kesintiler = pd.DataFrame(columns=TABLOLAR["kesintiler"])
kargo_faturalari = pd.DataFrame(columns=TABLOLAR["kargo_faturalari"])
yol = HAM / "trendyol_finans.json"
if yol.exists():
    with open(yol, encoding="utf-8") as f:
        finans = json.load(f)

    h = pd.DataFrame(finans["siparis_hareketleri"])
    finans_hareketleri = pd.DataFrame({
        "hareket_id": h.id,
        "islem_tarihi": tr_saati_seri(h.transactionDate),
        "islem_turu": h.transactionType,
        "barkod": h.barcode,
        "siparis_no": h.orderNumber,
        "paket_id": h.shipmentPackageId,
        "satir_id": h.orderLineItemId.map(kalem_satir),
        "kalem_id": h.orderLineItemId,
        "siparis_tarihi": tr_saati_seri(h.orderDate),
        "borc": h.debt,
        "alacak": h.credit,
        "komisyon_orani": h.commissionRate,
        "komisyon_tutari": h.commissionAmount,
        "satici_hakedisi": h.sellerRevenue,
        "vade_gun": h.paymentPeriod,
        "odeme_tarihi": tr_saati_seri(h.paymentDate),
        "ulke": h.country,
    })

    d = pd.DataFrame(finans["diger_hareketler"])
    kesintiler = pd.DataFrame({
        "kesinti_id": d.id,
        "islem_tarihi": tr_saati_seri(d.transactionDate),
        "tur": d.transactionType,
        "grup": d.transactionType.map(kesinti_grubu),
        "borc": d.debt,
        "alacak": d.credit,
        "aciklama": d.description,
        "odeme_tarihi": tr_saati_seri(d.paymentDate),
    })

    fatura_tarihi = dict(zip(d.commissionInvoiceSerialNumber.fillna(d.id), kesintiler.islem_tarihi))
    siparis_paket = siparisler.drop_duplicates("siparis_no", keep=False).set_index("siparis_no").paket_id
    k = pd.DataFrame([dict(x, fatura_no=no) for no, kalemler in finans["kargo_fatura_kalemleri"].items()
                      for x in kalemler])
    if len(k):
        kargo_faturalari = pd.DataFrame({
            "fatura_no": k.fatura_no,
            "fatura_tarihi": k.fatura_no.map(fatura_tarihi),
            "siparis_no": k.orderNumber,
            # önce kargo takip no, yoksa (tek paketli) sipariş no ile
            "paket_id": k.parcelUniqueId.map(takip_paket).fillna(k.orderNumber.astype(str).map(siparis_paket)),
            "gonderi_turu": k.shipmentPackageType,
            "desi": k.desi,
            "tutar": k.amount,
        })
else:
    print("UYARI: trendyol_finans.json yok, önce 'python -m cekim.finans' çalıştırın.")

# ====================================================
# 6) KAYDET
# ====================================================

print(f"Kaydediliyor: {CIKTI}")
kaydet(urunler, CIKTI, "urunler")
kaydet(siparisler, CIKTI, "siparisler")
kaydet(satirlar, CIKTI, "siparis_satirlari")
kaydet(pd.DataFrame(gecmis), CIKTI, "siparis_durum_gecmisi")
kaydet(pd.DataFrame(indirimler), CIKTI, "siparis_indirimleri")
kaydet(sorular, CIKTI, "sorular")
kaydet(urun_yorumlari, CIKTI, "urun_yorumlari")
kaydet(satici_yorumlari, CIKTI, "satici_yorumlari")
kaydet(iadeler, CIKTI, "iadeler")
kaydet(finans_hareketleri, CIKTI, "finans_hareketleri")
kaydet(kesintiler, CIKTI, "kesintiler")
kaydet(kargo_faturalari, CIKTI, "kargo_faturalari")

print("\nEşleşme kontrolü:")
print(f"  satır -> ürün (barkod)         : %{satirlar.barkod.isin(urunler.barkod).mean() * 100:.1f}")
print(f"  yorum -> ürün (icerik_id)      : %{urun_yorumlari.icerik_id.isin(urunler.icerik_id).mean() * 100:.1f}")
print(f"  soru  -> ürün (model_kodu)     : %{sorular.model_kodu.isin(urunler.model_kodu).mean() * 100:.1f}")


def oran(seri):
    return f"%{seri.mean() * 100:.1f}" if len(seri) else "-"


# Sipariş tablosu yalnızca son ~3 ayı ve Türkiye mağazasını kapsar; eski/yurt dışı kayıtlar bağlanmaz
pencere = siparisler.siparis_tarihi.min()
yeni_iade = iadeler[iadeler.siparis_tarihi >= pencere]
yeni_satis = finans_hareketleri[(finans_hareketleri.siparis_tarihi >= pencere) & (finans_hareketleri.ulke == "Türkiye")]
print(f"  iade  -> ürün (barkod)         : {oran(iadeler.barkod.isin(urunler.barkod))}")
print(f"  iade  -> satır (sipariş penceresi): {oran(yeni_iade.satir_id.isin(satirlar.satir_id))}")
print(f"  finans-> ürün (barkod)         : {oran(finans_hareketleri.barkod.isin(urunler.barkod))}")
print(f"  finans-> satır (pencere, TR)   : {oran(yeni_satis.satir_id.isin(satirlar.satir_id))}")
# Kargo faturası 2-5 hafta gecikmeli kesildiği için 45 günden eski gönderilere bakılır
eski = siparisler[siparisler.kargoya_verilis_tarihi < siparisler.siparis_tarihi.max() - pd.Timedelta(days=45)]
print(f"  paket -> kargo faturası (>45 gün): {oran(eski.paket_id.isin(kargo_faturalari.paket_id))}")
