"""Cari hesap hareketleri -> veri/ham/trendyol_finans.json

  siparis_hareketleri     satış, iade, indirim, kupon (sipariş kalemine bağlı)
  diger_hareketler        kargo/reklam/platform kesintileri, komisyon faturaları, ödemeler
  kargo_fatura_kalemleri  kargo faturalarının gönderi bazlı detayı

İlk çalıştırmada son 365 gün, sonrakilerde son 45 gün çekilir ve id ile birleştirilir.
Kargo faturası detayı yalnızca daha önce çekilmemiş faturalar için istenir.
"""
from datetime import datetime, timedelta

from cekim import anonim
from cekim.ayarlar import API, SATICI_ID, json_oku, json_yaz, ms, pencereler, resmi_basliklar, tum_sayfalar

DOSYA = "trendyol_finans.json"
URL = f"{API}/finance/che/sellers/{SATICI_ID}"
ILK_GUN, ARTIMLI_GUN = 365, 45

SIPARIS_TURLERI = ["Sale", "Return", "Discount", "DiscountCancel", "Coupon", "CouponCancel",
                   "ProvisionPositive", "ProvisionNegative", "ManualRefund"]
DIGER_TURLER = ["DeductionInvoices", "ReturnInvoice", "PaymentOrder", "CashAdvance", "WireTransfer",
                "IncomingTransfer", "CommissionAgreementInvoice", "FinancialItem"]


def calistir():
    basliklar = resmi_basliklar()
    mevcut = json_oku(DOSYA, {})
    siparis = {r["id"]: r for r in mevcut.get("siparis_hareketleri", [])}
    diger = {r["id"]: r for r in mevcut.get("diger_hareketler", [])}
    kargo = mevcut.get("kargo_fatura_kalemleri", {})
    gun = ARTIMLI_GUN if siparis else ILK_GUN
    onceki = len(siparis), len(diger)

    bitis = datetime.now()
    for bas, bit in pencereler(bitis, bitis - timedelta(days=gun), gun=15):   # API en fazla 15 gün
        aralik = {"startDate": ms(bas), "endDate": ms(bit)}
        sayac = {}
        for yol, turler, hedef in [("settlements", SIPARIS_TURLERI, siparis), ("otherfinancials", DIGER_TURLER, diger)]:
            sayac[yol] = 0
            for tur in turler:
                kayitlar = tum_sayfalar(f"{URL}/{yol}", {**aralik, "transactionType": tur}, basliklar, 1000)
                hedef.update({r["id"]: r for r in kayitlar})
                sayac[yol] += len(kayitlar)
        print(f"{bas:%d.%m.%Y} - {bit:%d.%m.%Y}: {sayac['settlements']} sipariş hareketi, "
              f"{sayac['otherfinancials']} diğer hareket")

    faturalar = [o.get("commissionInvoiceSerialNumber") or o["id"] for o in diger.values()
                 if "Kargo" in (o.get("transactionType") or "")]
    yeni_faturalar = [f for f in faturalar if f not in kargo]
    for i, no in enumerate(yeni_faturalar, 1):
        kargo[no] = [anonim.kargo_kalemi(x) for x in tum_sayfalar(f"{URL}/cargo-invoice/{no}/items", {}, basliklar, 1000)]
        if i % 50 == 0:
            print(f"Kargo faturası detayı: {i}/{len(yeni_faturalar)}")

    print(f"Toplam {len(siparis)} sipariş hareketi ({len(siparis) - onceki[0]:+d}), "
          f"{len(diger)} diğer hareket ({len(diger) - onceki[1]:+d}), {len(yeni_faturalar)} yeni kargo faturası.")
    json_yaz(DOSYA, {
        "siparis_hareketleri": sorted(siparis.values(), key=lambda r: r["transactionDate"]),
        "diger_hareketler": sorted(diger.values(), key=lambda r: r["transactionDate"]),
        "kargo_fatura_kalemleri": kargo,
    })


if __name__ == "__main__":
    calistir()
