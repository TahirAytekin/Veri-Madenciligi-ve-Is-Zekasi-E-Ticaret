"""Ürün ve satıcı değerlendirmeleri -> veri/ham/trendyol_urun_yorumlari.csv, trendyol_satici_yorumlari.csv

DİKKAT: Resmi API değil; trendyol.com/magaza/profil sayfasının arka planda kullandığı istekler.
Key gerekmez ama Trendyol değiştirirse bozulabilir ve sık kullanımda engellenebilir.
Haftada bir çalıştırmak yeterlidir (guncelle.py pazartesileri ya da --haftalik ile çalıştırır).
"""
from datetime import datetime

from cekim import anonim
from cekim.ayarlar import SATICI_ID, csv_yaz, gerekli, istek

URL = "https://apigw.trendyol.com/discovery-sellerstore-gateway-service/api/ugc"
ORTAK = {"sellerId": SATICI_ID, "countryCode": "TR", "language": "tr", "storefrontId": 1, "culture": "tr-TR"}
BEKLEME = 1.0   # her istek arası (saniye), siteyi yormamak için


def basliklar():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
        "Accept": "application/json",
        "Origin": "https://www.trendyol.com",
        "Referer": f"https://www.trendyol.com/magaza/profil/{gerekli('TRENDYOL_MAGAZA_ADI')}-m-{SATICI_ID}",
    }


def tarih(ms_deger):
    return datetime.fromtimestamp(ms_deger / 1000).strftime("%Y-%m-%d %H:%M") if ms_deger else ""


def hepsini_cek(yol, blok_adi, ek):
    """totalPages istekten isteğe değişebildiği için boş sayfa gelene kadar devam eder; tekrarları atar."""
    kayitlar, sayfa = {}, 0
    while True:
        veri = istek(f"{URL}/{yol}", {**ORTAK, **ek, "page": sayfa, "size": 20}, basliklar(), bekle=BEKLEME)
        icerik = veri[blok_adi]["content"]
        kayitlar.update({r["id"]: r for r in icerik})
        sayfa += 1
        if not icerik:
            print(f"{blok_adi}: {len(kayitlar)} kayıt ({sayfa} sayfa)")
            return list(kayitlar.values())


def oy(yorum, tur):
    for r in yorum.get("ratings", []):
        if r["voteType"] == tur:
            return r["vote"].get("rate"), ", ".join(r["vote"].get("reasons", []))
    return None, ""


def calistir():
    urun = hepsini_cek("product-reviews", "productReviews", {})
    csv_yaz("trendyol_urun_yorumlari.csv", [{
        "yorum_id": r["id"],
        "tarih": tarih(r.get("createdDate")),
        "contentId": r.get("contentId"),
        "urun": (r.get("product") or {}).get("title"),
        "puan": r.get("rate"),
        "yorum": anonim.metin(r.get("comment")),
        "beden": r.get("productSize"),
        "boy": (r.get("productAttributes") or {}).get("height"),
        "kilo": (r.get("productAttributes") or {}).get("weight"),
        "begeni": r.get("reviewLikeCount"),
        "fotografli": bool(r.get("mediaFiles")),
        "urun_linki": "https://www.trendyol.com" + (r.get("product") or {}).get("link", ""),
    } for r in urun])

    satici = hepsini_cek("seller-reviews", "sellerReviews",
                         {"pageSize": 20, "order": "desc", "orderBy": "lastEditedDate"})
    satirlar = []
    for r in satici:
        satici_puan, satici_neden = oy(r, "SELLER")
        kargo_puan, kargo_neden = oy(r, "CARGO")
        satirlar.append({
            "yorum_id": r["id"],
            "tarih": tarih(r.get("creationDate")),
            "satici_puani": satici_puan,
            "kargo_puani": kargo_puan,
            "yorum": anonim.metin(r.get("comment")),
            "satici_nedenleri": satici_neden,
            "kargo_nedenleri": kargo_neden,
            "satici_cevabi": r.get("customerSatisfactionResponse"),
            "platform": r.get("platform"),
        })
    csv_yaz("trendyol_satici_yorumlari.csv", satirlar)


if __name__ == "__main__":
    calistir()
