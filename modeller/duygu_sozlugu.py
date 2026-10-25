"""Duygu analizi için kelime listesi referansı (F2-06). Gerçek yorumlara bakılmadan, önceden kayıtla birlikte yazıldı;
sonuçlar görüldükten sonra değiştirilmez.

skor = (olumlu − olumsuz) / (olumlu + olumsuz + 1), [-1, 1]. Eşleşme kelime başından (kök) yapılır. Önce olumsuz
kalıplar (çok kelimeli ifadeler ve "olumlu kelime + değil") sayılıp metinden çıkarılır, sonra olumlu kelimeler sayılır.
"""
import re

OLUMLU = ["güzel", "harika", "mükemmel", "süper", "bayıldım", "beğendim", "memnun", "kaliteli", "tavsiye", "teşekkür",
          "şahane", "muhteşem", "rahat", "tam oldu", "çok iyi", "başarılı", "hızlı", "özenli", "sevdim", "efsane",
          "kusursuz", "uygun fiyat", "şık", "kaliteli", "yumuşak", "tam kalıp", "iyi"]
OLUMSUZ = ["tavsiye etmem", "tavsiye etmiyorum", "almayın", "hayal kırıklığı", "küçük geldi", "büyük geldi",
           "geç geldi", "kargo gecikti", "kötü", "berbat", "rezalet", "beğenmedim", "iade", "kalitesiz", "yırtık",
           "sökük", "leke", "defolu", "pişman", "vasat", "olmadı", "gelmedi", "yanlış", "eksik", "sahte",
           "kullanışsız", "solmuş", "tüylen", "çekti", "ince", "dar", "bol", "kalitesi düşük", "değmez", "sorun"]
_OLUMSUZ_DESEN = re.compile(r"\b(" + "|".join(sorted(map(re.escape, OLUMSUZ), key=len, reverse=True)) + r")\w*")
_DEGIL_DESEN = re.compile(r"\b(" + "|".join(map(re.escape, OLUMLU)) + r")\w*\s+değil\w*")
_OLUMLU_DESEN = re.compile(r"\b(" + "|".join(sorted(map(re.escape, set(OLUMLU)), key=len, reverse=True)) + r")\w*")


def kucult(metin):
    """Türkçe küçük harf (I -> ı, İ -> i)."""
    return str(metin).replace("I", "ı").replace("İ", "i").lower()


def sozluk_skoru(metin):
    m = kucult(metin)
    olumsuz = len(_DEGIL_DESEN.findall(m))
    m = _DEGIL_DESEN.sub(" ", m)
    olumsuz += len(_OLUMSUZ_DESEN.findall(m))
    m = _OLUMSUZ_DESEN.sub(" ", m)
    olumlu = len(_OLUMLU_DESEN.findall(m))
    return (olumlu - olumsuz) / (olumlu + olumsuz + 1)
