"""Bilgi tabanı araması (F4-02): yerel embedding, BM25 ve ikisinin birleşimi (RRF).

    python -m asistan.arama --veri sahte --soru "iade oranı nasıl hesaplanıyor"
    python -m asistan.arama --degerlendir          # 5 yöntem, test seti: asistan/degerlendirme/arama_sorulari.json

    from asistan.arama import ara
    ara("katkı payı ne demek", veri="sahte", k=5)     # [{id, tur, baslik, metin, ..., skor}, ...]

Embedding'ler yerelde hesaplanır (metin bilgisayardan çıkmaz) ve ciktilar/<veri>/indeks/<yöntem>.npy dosyasında
saklanır; parçalar değişince (içerik özeti) yeniden hesaplanır. Seçilen yöntem SECILEN (bkz. docs/modeller/F4-02.md).
"""
import argparse
import hashlib
import json
import math
import re
import time
from collections import Counter
from functools import lru_cache

import numpy as np

from asistan import bilgi_tabani
from hazirlama.ortak import PROJE, VERI
from modeller.duygu_sozlugu import kucult

MODELLER = {"e5_kucuk": "intfloat/multilingual-e5-small", "e5_buyuk": "intfloat/multilingual-e5-base"}
YONTEMLER = ["e5_kucuk", "e5_buyuk", "bm25", "hibrit_kucuk", "hibrit_buyuk"]
SECILEN = "e5_buyuk"                # F4-02 seçim kuralının sonucu (docs/modeller/F4-02.md)
KOK_UZUNLUGU = 5
RRF_K = 60
TEST_SETI = PROJE / "asistan" / "degerlendirme" / "arama_sorulari.json"


# ====================================================
# 1) METİN VE BM25
# ====================================================

def _metin(p):
    return f"{p['baslik']}\n{p['metin']}"


def kokler(metin):
    """Türkçe için kaba kök: küçük harf, harf/rakam dizileri, ilk KOK_UZUNLUGU karakter."""
    return [t[:KOK_UZUNLUGU] for t in re.findall(r"[a-zçğıöşü0-9]+", kucult(metin))]


class BM25:
    def __init__(self, belgeler, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.belgeler = [Counter(kokler(d)) for d in belgeler]
        self.uzunluk = np.array([sum(c.values()) for c in self.belgeler], dtype=float)
        self.ort = self.uzunluk.mean() if len(self.uzunluk) else 0.0
        df = Counter(t for c in self.belgeler for t in c)
        n = len(self.belgeler)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def skorlar(self, sorgu):
        s = np.zeros(len(self.belgeler))
        for t in set(kokler(sorgu)):
            if t not in self.idf:
                continue
            tf = np.array([c.get(t, 0) for c in self.belgeler], dtype=float)
            s += self.idf[t] * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * self.uzunluk / self.ort))
        return s


# ====================================================
# 2) EMBEDDING
# ====================================================

@lru_cache(maxsize=2)
def _model(ad):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODELLER[ad])


def _ozet(parcalar):
    return hashlib.sha256("\n".join(_metin(p) for p in parcalar).encode("utf-8")).hexdigest()[:16]


def gommeler(veri, parcalar, ad):
    """Parça vektörleri (normalize); önbellek ciktilar/<veri>/indeks/<ad>.npy, parça içeriği değişirse yenilenir."""
    klasor = bilgi_tabani.yol(veri).parent
    yol, ozet_yolu = klasor / f"{ad}.npy", klasor / f"{ad}.ozet"
    ozet = _ozet(parcalar)
    if yol.exists() and ozet_yolu.exists() and ozet_yolu.read_text() == ozet:
        return np.load(yol)
    v = _model(ad).encode([f"passage: {_metin(p)}" for p in parcalar], normalize_embeddings=True, batch_size=32,
                          show_progress_bar=False)
    np.save(yol, v)
    ozet_yolu.write_text(ozet)
    return v


def _sorgu_vektoru(ad, sorgu):
    return _model(ad).encode([f"query: {sorgu}"], normalize_embeddings=True, show_progress_bar=False)[0]


# ====================================================
# 3) ARAMA
# ====================================================

class Dizin:
    """Bir veri setinin parçaları üzerinde tüm yöntemler."""

    def __init__(self, veri):
        self.veri = veri
        self.parcalar = bilgi_tabani.oku(veri)
        self.bm25 = BM25([_metin(p) for p in self.parcalar])
        self._vektor = {}

    def vektorler(self, ad):
        if ad not in self._vektor:
            self._vektor[ad] = gommeler(self.veri, self.parcalar, ad)
        return self._vektor[ad]

    def siralama(self, sorgu, yontem):
        """Parça indeksleri, en iyiden kötüye; ve skorlar."""
        if yontem in MODELLER:
            s = self.vektorler(yontem) @ _sorgu_vektoru(yontem, sorgu)
        elif yontem == "bm25":
            s = self.bm25.skorlar(sorgu)
        elif yontem.startswith("hibrit_"):
            yogun = "e5_" + yontem.split("_")[1]
            s = np.zeros(len(self.parcalar))
            for alt in (yogun, "bm25"):
                sira, _ = self.siralama(sorgu, alt)
                s[sira] += 1 / (RRF_K + np.arange(1, len(sira) + 1))
        else:
            raise ValueError(f"bilinmeyen yöntem: {yontem}")
        sira = np.argsort(-s, kind="stable")
        return sira, s

    def ara(self, sorgu, k=5, yontem=SECILEN, tur=None):
        sira, s = self.siralama(sorgu, yontem)
        sonuc = []
        for i in sira:
            p = self.parcalar[i]
            if tur and p["tur"] not in (tur if isinstance(tur, (list, tuple, set)) else [tur]):
                continue
            sonuc.append({**p, "skor": float(s[i])})
            if len(sonuc) == k:
                break
        return sonuc


@lru_cache(maxsize=2)
def dizin(veri):
    return Dizin(veri)


def ara(sorgu, veri="sahte", k=5, yontem=SECILEN, tur=None):
    return dizin(veri).ara(sorgu, k, yontem, tur)


# ====================================================
# 4) DEĞERLENDİRME (önceden kayıtlı test seti)
# ====================================================

def eslesir(p, hedef):
    if "id" in hedef:
        return p["id"] == hedef["id"]
    if "id_onek" in hedef:
        return p["id"].startswith(hedef["id_onek"])
    if p["kaynak"] != hedef.get("kaynak"):
        return False
    return "baslik_icerir" not in hedef or kucult(hedef["baslik_icerir"]) in kucult(p["baslik"])


def degerlendir(veri, yontemler=YONTEMLER):
    d = dizin(veri)
    sorular = [q for q in json.loads(TEST_SETI.read_text(encoding="utf-8"))["sorular"]
               if any(eslesir(p, h) for p in d.parcalar for h in q["hedef"])]
    sonuc = {}
    for y in yontemler:
        d.siralama("ısınma", y)                               # model yükleme ve vektörler süreye girmesin
        bas, isabet, rr, ayrinti = time.time(), [], [], []
        for q in sorular:
            sira, _ = d.siralama(q["soru"], y)
            konum = next((r for r, i in enumerate(sira[:10], 1)
                          if any(eslesir(d.parcalar[i], h) for h in q["hedef"])), None)
            isabet.append(konum is not None and konum <= 5)
            rr.append(1 / konum if konum else 0.0)
            ayrinti.append({"soru": q["soru"], "konum": konum})
        sonuc[y] = {"isabet_5": float(np.mean(isabet)), "mrr_10": float(np.mean(rr)), "soru": len(sorular),
                    "sorgu_ms": round((time.time() - bas) / len(sorular) * 1000, 1), "ayrinti": ayrinti}
    return sonuc


def sec(sonuc):
    """Seçim kuralı: isabet@5, sonra MRR@10, sonra hız."""
    return max(sonuc, key=lambda y: (sonuc[y]["isabet_5"], sonuc[y]["mrr_10"], -sonuc[y]["sorgu_ms"]))


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--veri", default="sahte", choices=["sahte", "gercek"])
    p.add_argument("--soru")
    p.add_argument("--yontem", default=SECILEN, choices=YONTEMLER)
    p.add_argument("--degerlendir", action="store_true")
    a = p.parse_args()
    if a.degerlendir:
        tum = {v: degerlendir(v) for v in ["sahte", "gercek"] if (VERI / v / "siparisler.csv").exists()}
        for v, s in tum.items():
            print(f"\n{v}:")
            for y, r in s.items():
                print(f"  {y:13s} isabet@5 {r['isabet_5']:.3f}  MRR@10 {r['mrr_10']:.3f}  ({r['soru']} soru, "
                      f"{r['sorgu_ms']} ms/sorgu)")
        print(f"\nSeçim kuralına göre (sahte): {sec(tum['sahte'])}")
        hedef = bilgi_tabani.yol("sahte").parent / "arama_degerlendirme.json"
        hedef.write_text(json.dumps(tum, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        for r in ara(a.soru, a.veri, yontem=a.yontem):
            print(f"{r['skor']:.4f}  [{r['tur']}] {r['baslik']}")
