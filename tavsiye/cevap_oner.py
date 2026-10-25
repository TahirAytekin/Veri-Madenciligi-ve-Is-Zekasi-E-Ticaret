"""Müşteri sorusu cevap önerici (F3-04): soru → konu, boy-kilo → beden önerisi + kalıp + stok → cevap taslağı.

Kritik bilgiler kodla hesaplanır (konu, boy-kilo, önerilen beden, kalıp, stoktaki bedenler); LLM yalnızca bu bilgileri
mağazanın üslubunda cümleye döker ve yeni bilgi eklemez. API anahtarı yoksa şablon taslak döner.
"""
import re

from hazirlama.ortak import soru_konusu
from modeller.duygu_sozlugu import kucult
from modeller.ortak.ozellikler import HARF_SIRASI

MAKUL_BOY, MAKUL_KILO = (140, 210), (35, 150)
_SAYI = re.compile(r"(?<![\d.,])(\d[.,]\d{2}|\d{2,3})(?![\d.,]*\d)")
_BIRIM = {"boy": "boy", "boyum": "boy", "boyunda": "boy", "boyunuz": "boy", "cm": "boy",
          "kilo": "kilo", "kilom": "kilo", "kiloyum": "kilo", "kg": "kilo", "kl": "kilo", "k": "kilo",
          "ağırlığım": "kilo", "agirligim": "kilo"}
_BIRIM_SONRA = re.compile(r"^\s*([a-zğüşıöç]+)")
_BIRIM_ONCE = re.compile(r"([a-zğüşıöç]+)\s*:?\s*$")
_BEDEN_BUYUK = re.compile(r"(?<!\w)(3XL|2XL|XXL|XL|XXS|2XS|XS|S|M|L)(?!\w)")
_BEDEN_KUCUK = re.compile(r"(?<!\w)(3xl|2xl|xxl|xl|xxs|2xs|xs|s|m|l)\s+beden")


# ====================================================
# 1) SORUDAN VE CEVAPTAN BİLGİ ÇIKARMA
# ====================================================

def boy_kilo(metin):
    """Sorudaki boy (cm) ve kilo; bulunamayan None. '165 boy 58 kilo', '1.65 boy 58 kg', '165/58', 'boyum 170 kilom 70'."""
    m = kucult(metin)
    boy = kilo = None
    sayilar = []
    for e in _SAYI.finditer(m):
        once, sonra = _BIRIM_ONCE.search(m[:e.start()]), _BIRIM_SONRA.match(m[e.end():])
        sayilar.append((e.group(1), _BIRIM.get(once.group(1)) if once else None,
                        _BIRIM.get(sonra.group(1)) if sonra else None))
    # Türkçede birim sayıdan önce ("boyum 160 kilom 52") ya da sonra ("160 boy 52 kilo") gelir; bir cümlede yazım
    # tutarlıdır. İlk sayının önünde birim varsa "önde" düzeni, yoksa "arkada" düzeni kullanılır.
    onde = bool(sayilar) and sayilar[0][1] is not None
    adaylar = []
    for ham, birim_once, birim_sonra in sayilar:
        if re.fullmatch(r"\d[.,]\d{2}", ham):
            adaylar.append([round(float(ham.replace(",", ".")) * 100), "boy"])
        else:
            adaylar.append([int(ham), (birim_once or birim_sonra) if onde else (birim_sonra or birim_once)])
    for a in adaylar:                       # birimsiz sayılar: aralığa göre
        if a[1] is None:
            if MAKUL_BOY[0] <= a[0] <= MAKUL_BOY[1] and not any(x[1] == "boy" for x in adaylar):
                a[1] = "boy"
            elif MAKUL_KILO[0] <= a[0] <= MAKUL_KILO[1] and not any(x[1] == "kilo" for x in adaylar):
                a[1] = "kilo"
    for deger, tur in adaylar:
        if tur == "boy" and boy is None and MAKUL_BOY[0] <= deger <= MAKUL_BOY[1]:
            boy = deger
        elif tur == "kilo" and kilo is None and MAKUL_KILO[0] <= deger <= MAKUL_KILO[1]:
            kilo = deger
    return boy, kilo


def cevaptaki_bedenler(cevap):
    """Satıcı cevabında geçen harf bedenler (sıralı, tekil): 'M', 'XL' ... Büyük harfle yazılmış ya da 'beden' ile."""
    metin = str(cevap or "")
    bulunan = [b.upper() for b in _BEDEN_BUYUK.findall(metin)] + \
              [b.upper() for b in _BEDEN_KUCUK.findall(kucult(metin))]
    bulunan = ["2XL" if b == "XXL" else "2XS" if b == "XXS" else b for b in bulunan]
    return list(dict.fromkeys(b for b in bulunan if b in HARF_SIRASI))


def konu(metin):
    return soru_konusu(metin)
