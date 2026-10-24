"""İade talepleri (claims) -> veri/ham/trendyol_iadeler.json

İlk çalıştırmada mağazanın açılışına kadar tüm geçmiş (üst üste boş pencereler gelene kadar),
sonrakilerde son 45 gün çekilir (kabul/iptal gibi durum değişiklikleri güncellenir) ve id ile birleştirilir.
"""
from datetime import datetime, timedelta

from cekim import anonim
from cekim.ayarlar import API, SATICI_ID, istek, json_oku, json_yaz, ms, resmi_basliklar

DOSYA = "trendyol_iadeler.json"
URL = f"{API}/order/sellers/{SATICI_ID}/claims"
ARTIMLI_GUN = 45
BOS_PENCERE_SINIRI = 3


def pencere_cek(bas, bit, basliklar):
    talepler, sayfa = [], 0
    while True:
        veri = istek(URL, {"startDate": ms(bas), "endDate": ms(bit), "page": sayfa, "size": 50}, basliklar)
        talepler.extend(veri.get("content") or [])   # açılıştan önceki dönemlerde içerik None gelir
        sayfa += 1
        if sayfa >= (veri.get("totalPages") or 0):
            return talepler


def calistir():
    basliklar = resmi_basliklar()
    talepler = {c["id"]: c for c in json_oku(DOSYA, [])}
    onceki = len(talepler)
    sinir = datetime.now() - timedelta(days=ARTIMLI_GUN) if talepler else None

    bitis, bos = datetime.now(), 0
    while (bitis > sinir) if sinir else (bos < BOS_PENCERE_SINIRI):
        bas = bitis - timedelta(weeks=2)
        yeni = pencere_cek(bas, bitis, basliklar)
        talepler.update({c["id"]: anonim.iade(c) for c in yeni})   # kişisel veri diske yazılmaz
        print(f"{bas:%d.%m.%Y} - {bitis:%d.%m.%Y}: {len(yeni)} iade talebi")
        bos = bos + 1 if not yeni else 0
        bitis = bas

    print(f"Toplam {len(talepler)} iade talebi ({len(talepler) - onceki:+d} yeni).")
    json_yaz(DOSYA, sorted(talepler.values(), key=lambda c: c["claimDate"]))


if __name__ == "__main__":
    calistir()
