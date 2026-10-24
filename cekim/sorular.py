"""Müşteri soruları ve cevapları -> veri/ham/trendyol_sorular.csv

İlk çalıştırmada son 12 hafta, sonrakilerde son 4 hafta çekilir (yeni cevaplar güncellenir)
ve mevcut dosyayla soru_id üzerinden birleştirilir.
"""
from datetime import datetime, timedelta

from cekim import anonim
from cekim.ayarlar import API, SATICI_ID, csv_oku, csv_yaz, ms, pencereler, resmi_basliklar, tum_sayfalar

DOSYA = "trendyol_sorular.csv"
URL = f"{API}/qna/sellers/{SATICI_ID}/questions/filter"
ILK_HAFTA, ARTIMLI_HAFTA = 12, 4


def tarih(ms_deger):
    return datetime.fromtimestamp(ms_deger / 1000).strftime("%Y-%m-%d %H:%M") if ms_deger else ""


def calistir():
    basliklar = resmi_basliklar()
    mevcut = {s["soru_id"]: s for s in csv_oku(DOSYA)}
    hafta = ARTIMLI_HAFTA if mevcut else ILK_HAFTA
    onceki = len(mevcut)

    bitis = datetime.now()
    for bas, bit in pencereler(bitis, bitis - timedelta(weeks=hafta), gun=14):   # API en fazla 2 hafta
        sorular = tum_sayfalar(URL, {"supplierId": SATICI_ID, "startDate": ms(bas), "endDate": ms(bit),
                                     "orderByField": "CreatedDate", "orderByDirection": "DESC"},
                               basliklar, boyut=50)
        print(f"{bas:%d.%m.%Y} - {bit:%d.%m.%Y}: {len(sorular)} soru")
        for q in sorular:
            cevap = q.get("answer") or {}
            mevcut[str(q.get("id"))] = {
                "soru_id": q.get("id"),
                "tarih": tarih(q.get("creationDate")),
                "urun": q.get("productName"),
                "productMainId": q.get("productMainId"),
                "soru": anonim.metin(q.get("text")),
                "durum": q.get("status"),
                "cevap": cevap.get("text"),
                "cevap_tarihi": tarih(cevap.get("creationDate")),
                "urun_linki": q.get("webUrl"),
            }

    print(f"Toplam {len(mevcut)} soru ({len(mevcut) - onceki:+d} yeni).")
    csv_yaz(DOSYA, sorted(mevcut.values(), key=lambda s: s["tarih"], reverse=True))


if __name__ == "__main__":
    calistir()
