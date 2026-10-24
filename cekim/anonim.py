"""Kişisel verileri diske yazılmadan önce ayıklar (KVKK veri minimizasyonu).

Analizde kullanılmayan kişisel alanlar silinir; bağlantı için gereken kimlikler tek yönlü özetle değiştirilir:
  silinir           ad-soyad, açık adres, mahalle, posta kodu, telefon, e-posta, TC/vergi no, fatura adresi
                    ve fatura linki, kargo takip linki, gönderici no, teslimat kodu
  özetlenir         müşteri ID (tekrar alan müşteri analizi), kargo takip no (kargo faturası -> paket bağlantısı)
  tutulur           il, ilçe; ürün, tutar, tarih ve durum bilgileri
  serbest metin     müşteri notlarında/sorularda/yorumlarda geçen telefon, e-posta ve TC numaraları gizlenir

Çekim betikleri kayıtları bu modülden geçirerek yazar. Mevcut ham dosyaları bir kez temizlemek için:
  python -m cekim.anonim
Tüm fonksiyonlar tekrar çalıştırılabilir (zaten temizlenmiş kaydı değiştirmez).
"""
import hashlib
import re

from cekim.ayarlar import csv_oku, csv_yaz, gerekli, json_oku, json_yaz

ADRES_TUTULAN = {"city", "cityCode", "district", "districtId", "countryCode"}
SIPARIS_SILINEN = {"customerFirstName", "customerLastName", "customerEmail", "identityNumber", "taxNumber",
                   "invoiceAddress", "invoiceLink", "invoiceNumber", "cargoTrackingLink", "cargoSenderNumber",
                   "sellerOtpCode"}
IADE_SILINEN = {"customerFirstName", "customerLastName", "cargoTrackingLink", "cargoSenderNumber", "sellerOtp"}

_TELEFON = re.compile(r"(?:\+?90[\s.-]?)?\(?0?5\d{2}\)?[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}")
_EPOSTA = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_TC = re.compile(r"\b[1-9]\d{10}\b")


def _gecerli_tc(numara):
    """TC kimlik no doğrulama algoritması; aynı uzunluktaki sipariş numaralarını ayırt eder."""
    r = [int(c) for c in numara]
    return r[9] == (sum(r[0:9:2]) * 7 - sum(r[1:8:2])) % 10 and r[10] == sum(r[:10]) % 10


def ozet(on_ek, deger, uzunluk=10, alan=""):
    """Tek yönlü özet (ör. M3f9a...). hazirlama/temizle.py'deki müşteri ID özetiyle aynı yöntem ve tuz."""
    if deger in (None, ""):
        return None
    deger = str(deger)
    if deger.startswith(on_ek) and len(deger) == len(on_ek) + uzunluk:
        return deger   # zaten özetlenmiş
    return on_ek + hashlib.sha256(f"{gerekli('MUSTERI_ID_TUZ')}{alan}{deger}".encode()).hexdigest()[:uzunluk]


def takip_no(deger):
    return ozet("K", deger, 12, "kargo")


def metin(deger):
    """Serbest metindeki telefon, e-posta ve TC numaralarını gizler."""
    if not isinstance(deger, str) or not deger:
        return deger
    deger = _EPOSTA.sub("[gizlendi]", deger)
    deger = _TELEFON.sub("[gizlendi]", deger)
    return _TC.sub(lambda m: "[gizlendi]" if _gecerli_tc(m.group()) else m.group(), deger)


def siparis(o):
    for alan in SIPARIS_SILINEN:
        o.pop(alan, None)
    o["shipmentAddress"] = {k: v for k, v in (o.get("shipmentAddress") or {}).items() if k in ADRES_TUTULAN}
    o["customerId"] = ozet("M", o.get("customerId"))
    o["cargoTrackingNumber"] = takip_no(o.get("cargoTrackingNumber"))
    return o


def iade(c):
    for alan in IADE_SILINEN:
        c.pop(alan, None)
    c["cargoTrackingNumber"] = takip_no(c.get("cargoTrackingNumber"))
    reddedilen = c.get("rejectedPackageInfo")
    if isinstance(reddedilen, dict):
        for alan in IADE_SILINEN:
            reddedilen.pop(alan, None)
        reddedilen["cargoTrackingNumber"] = takip_no(reddedilen.get("cargoTrackingNumber"))
    for kalem in c.get("items") or []:
        for ci in kalem.get("claimItems") or []:
            ci["customerNote"] = metin(ci.get("customerNote"))
            ci["note"] = metin(ci.get("note"))
    return c


def kargo_kalemi(x):
    x["parcelUniqueId"] = takip_no(x.get("parcelUniqueId"))
    return x


# ====================================================
# MEVCUT HAM DOSYALARI TEMİZLE
# ====================================================

def calistir():
    siparisler = json_oku("trendyol_tum_siparisler.json")
    if siparisler is not None:
        json_yaz("trendyol_tum_siparisler.json", [siparis(o) for o in siparisler])

    iadeler = json_oku("trendyol_iadeler.json")
    if iadeler is not None:
        json_yaz("trendyol_iadeler.json", [iade(c) for c in iadeler])

    finans = json_oku("trendyol_finans.json")
    if finans is not None:
        finans["kargo_fatura_kalemleri"] = {no: [kargo_kalemi(x) for x in kalemler]
                                            for no, kalemler in finans["kargo_fatura_kalemleri"].items()}
        json_yaz("trendyol_finans.json", finans)

    for dosya, alanlar in [("trendyol_sorular.csv", ["soru"]), ("trendyol_urun_yorumlari.csv", ["yorum"]),
                           ("trendyol_satici_yorumlari.csv", ["yorum"])]:
        satirlar = csv_oku(dosya)
        if satirlar:
            csv_yaz(dosya, [{**s, **{a: metin(s[a]) for a in alanlar}} for s in satirlar])


if __name__ == "__main__":
    calistir()
