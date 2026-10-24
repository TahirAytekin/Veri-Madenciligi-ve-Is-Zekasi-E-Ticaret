"""Ürün kataloğu -> veri/ham/trendyol_urunler.csv (+ günlük fiyat/stok kaydı)

API geçmiş fiyat ve stok vermez. Her çalıştırmada o günün fiyat ve stokları
veri/ham/urun_gecmisi/YYYY-MM-DD.csv.gz olarak saklanır; günlük çalıştırılırsa fiyat/stok geçmişi birikir.

Eşleşen alanlar:
  productCode       -> siparişlerdeki lines.productCode
  productContentId  -> ürün yorumlarındaki contentId (ürün sayfası)
  productMainId     -> müşteri sorularındaki productMainId (model kodu)
"""
from datetime import datetime

from cekim.ayarlar import API, SATICI_ID, csv_yaz, resmi_basliklar, tum_sayfalar

DOSYA = "trendyol_urunler.csv"
URL = f"{API}/product/sellers/{SATICI_ID}/products"


def ozellik(urun, ad):
    for a in urun.get("attributes", []):
        if a.get("attributeName") == ad:
            return a.get("attributeValue")
    return None


def calistir():
    urunler = tum_sayfalar(URL, {}, resmi_basliklar())
    print(f"Toplam {len(urunler)} ürün varyantı alındı.")

    csv_yaz(DOSYA, [{
        "barcode": p.get("barcode"),
        "productCode": p.get("productCode"),
        "productContentId": p.get("productContentId"),
        "productMainId": p.get("productMainId"),
        "stockCode": p.get("stockCode"),
        "title": p.get("title"),
        "categoryName": p.get("categoryName"),
        "renk": ozellik(p, "Renk"),
        "beden": ozellik(p, "Beden"),
        "listPrice": p.get("listPrice"),
        "salePrice": p.get("salePrice"),
        "stok": p.get("quantity"),
        "onSale": p.get("onSale"),
        "archived": p.get("archived"),
        "createDateTime": p.get("createDateTime"),
        "productUrl": p.get("productUrl"),
    } for p in urunler])

    an = datetime.now()
    csv_yaz(f"urun_gecmisi/{an:%Y-%m-%d}.csv.gz", [{
        "kayit_zamani": f"{an:%Y-%m-%d %H:%M}",
        "barcode": p.get("barcode"),
        "listPrice": p.get("listPrice"),
        "salePrice": p.get("salePrice"),
        "stok": p.get("quantity"),
        "onSale": p.get("onSale"),
        "archived": p.get("archived"),
    } for p in urunler], sikistir=True)


if __name__ == "__main__":
    calistir()
