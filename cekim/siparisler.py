"""Siparişler (kargo paketleri) -> veri/ham/trendyol_tum_siparisler.json

Trendyol sipariş API'si yalnızca son ~3 ayı verir. Her çalıştırmada erişilebilen dönem yeniden çekilir
(durumu değişen paketler güncellenir) ve mevcut dosyayla birleştirilir; böylece 3 aydan eski siparişler
kaybolmaz, geçmiş zamanla birikir.
"""
from datetime import datetime, timedelta

from cekim import anonim
from cekim.ayarlar import API, SATICI_ID, istek, json_oku, json_yaz, ms, resmi_basliklar

DOSYA = "trendyol_tum_siparisler.json"
URL = f"{API}/order/sellers/{SATICI_ID}/v2/orders"   # 15 Ekim 2026'dan itibaren zorunlu v2 adresi
BOS_PENCERE_SINIRI = 3   # üst üste bu kadar boş 2 haftalık pencere gelirse dur


def calistir():
    basliklar = resmi_basliklar(storeFrontCode="TR")
    paketler = {o["shipmentPackageId"]: o for o in json_oku(DOSYA, [])}
    onceki = len(paketler)

    bitis, bos = datetime.now(), 0
    while bos < BOS_PENCERE_SINIRI:
        bas = bitis - timedelta(weeks=2)   # API tek istekte en fazla 2 haftalık aralık kabul ediyor
        sayfa, adet = 0, 0
        while True:
            veri = istek(URL, {"startDate": ms(bas), "endDate": ms(bitis), "page": sayfa, "size": 200}, basliklar)
            for o in veri.get("content") or []:
                paketler[o["shipmentPackageId"]] = anonim.siparis(o)   # kişisel veri diske yazılmaz
            adet += len(veri.get("content") or [])
            sayfa += 1
            if sayfa >= (veri.get("totalPages") or 0) or sayfa >= 50:
                break
        print(f"{bas:%d.%m.%Y} - {bitis:%d.%m.%Y}: {adet} paket")
        bos = bos + 1 if adet == 0 else 0
        bitis = bas

    print(f"Toplam {len(paketler)} paket ({len(paketler) - onceki:+d} yeni).")
    json_yaz(DOSYA, sorted(paketler.values(), key=lambda o: o["orderDate"]))


if __name__ == "__main__":
    calistir()
