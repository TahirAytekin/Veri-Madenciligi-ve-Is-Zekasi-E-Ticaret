"""Yorum duygu analizi (F2-06): hazır Türkçe BERT (sıfır atış) ve kelime listesi referansı; olumsuz yorumlarda konu.

    python -m modeller.duygu

Tasarım ve başarı ölçütü çalıştırmadan önce docs/modeller/F2-06.md'ye, kelime listesi modeller/duygu_sozlugu.py'ye
yazıldı. Model eğitilmez; etiket puandan gelir (1–2 olumsuz, 4–5 olumlu, 3 ölçüt dışı).

Çıktılar (ciktilar/, git'e girmez):
    <veri>/tahminler/F2-06.csv                yorum başına BERT olumlu olasılığı, şikâyet işareti, sözlük skoru, konular
    <veri>/tahminler/F2-06_urun.csv           ürün başına yorum duygu özeti ve en sık şikâyet konusu
    <veri>/dogrulama/F2-06.json               ölçütler
"""
import json
import re
from functools import lru_cache

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score

from analiz import metrikler as m
from hazirlama.kalibrasyon import _birimler
from hazirlama.ortak import VERI
from modeller.duygu_sozlugu import kucult, sozluk_skoru
from modeller.ortak.degerlendir import CIKTILAR, bootstrap_auc_farki, siniflandirma_olcutleri
from modeller.ortak.kayit import tahmin_kaydet

MODEL_ID = "F2-06"
DUYGU_MODELI = "savasy/bert-base-turkish-sentiment-cased"
EN_COK_TOKEN = 128
MIN_URUN_YORUMU = 3

# Olumsuz yorumlarda şikâyet konusu (kural tabanlı; çalıştırmadan önce sabitlendi). Bir yorum birden çok konu alabilir.
KONULAR = {
    "beden_kalip": r"beden|kalıp|\bdar\b|\bbol\b|küçük geldi|büyük geldi|uzun|kısa|olmadı",
    "kumas_kalite": r"kumaş|kalite|\bince\b|terlet|tüylen|dikiş|sökük|yırtık|çekti|solmuş",
    "kargo_paket": r"kargo|paket|geç geldi|teslim|gelmedi|kutu",
    "renk_gorsel": r"renk|fotoğraf|görsel|resim|farklı geldi",
    "fiyat": r"fiyat|pahalı|ucuz|değmez|\bpara",
    "urun_hatasi": r"defolu|leke|bozuk|eksik|yanlış|hatalı",
}


# ====================================================
# 1) VERİ
# ====================================================

def yorum_tablosu(veri):
    """Ürün ve satıcı yorumları tek tabloda: kaynak, puan (satıcıda satıcı puanı), metin, ürün (varsa), etiket."""
    t = m.tablolar(veri)
    u = t["urunler"].dropna(subset=["icerik_id"]).drop_duplicates("icerik_id").set_index("icerik_id")
    urun = t["urun_yorumlari"].assign(kaynak="urun", model_kodu=lambda x: x.icerik_id.map(u.model_kodu))
    satici = t["satici_yorumlari"].rename(columns={"satici_puani": "puan"}).assign(kaynak="satici", model_kodu=None)
    sutunlar = ["yorum_id", "kaynak", "yorum_tarihi", "model_kodu", "puan", "yorum"]
    y = pd.concat([urun[sutunlar], satici[sutunlar]], ignore_index=True)
    y = y[y.yorum.fillna("").str.strip().str.len() > 0].reset_index(drop=True)
    y["etiket"] = np.select([y.puan <= 2, y.puan >= 4], [0, 1], np.nan)
    return y


# ====================================================
# 2) SKORLAR
# ====================================================

@lru_cache(maxsize=1)
def _bert():
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(DUYGU_MODELI)
    model = AutoModelForSequenceClassification.from_pretrained(DUYGU_MODELI).eval()
    return tok, model


def bert_skoru(metinler, yigin=16):
    """P(olumlu) — modelin 1 numaralı etiketi 'positive'."""
    import torch
    tok, model = _bert()
    sonuc = []
    metinler = [str(x) for x in metinler]
    with torch.no_grad():
        for i in range(0, len(metinler), yigin):
            girdi = tok(metinler[i:i + yigin], padding=True, truncation=True, max_length=EN_COK_TOKEN,
                        return_tensors="pt")
            sonuc.append(torch.softmax(model(**girdi).logits, dim=-1)[:, 1].numpy())
    return np.concatenate(sonuc) if sonuc else np.array([])


def konular(metin):
    k = kucult(metin)
    return ",".join(ad for ad, desen in KONULAR.items() if re.search(desen, k))


def skorla(veri):
    y = yorum_tablosu(veri)
    y["bert_olumlu"] = bert_skoru(y.yorum)
    y["sozluk"] = y.yorum.map(sozluk_skoru)
    # BERT'in "olumsuz"u yorumun genel puanından çok metindeki şikâyeti yakalıyor ("güzel ama kalıbı dar"; bkz. model
    # kartı). Bu yüzden genel duygu puandan alınır; BERT şikâyet işareti ve konu çıkarma için kullanılır.
    y["sikayet_iceriyor"] = y.bert_olumlu < 0.5
    y["konular"] = np.where(y.sikayet_iceriyor, y.yorum.map(konular), "")
    return y


# ====================================================
# 3) DEĞERLENDİRME
# ====================================================

def _olcutler(d):
    y = d.etiket.astype(int)
    return {"n": int(len(d)), "olumsuz": int((y == 0).sum()), "olumlu": int((y == 1).sum()),
            "bert_auc": siniflandirma_olcutleri(y, d.bert_olumlu)["roc_auc"],
            "sozluk_auc": siniflandirma_olcutleri(y, d.sozluk)["roc_auc"],
            "bert_makro_f1": float(f1_score(y, d.bert_olumlu >= 0.5, average="macro")),
            "sozluk_makro_f1": float(f1_score(y, d.sozluk >= 0, average="macro")),   # 0 (eşleşme yok) olumlu sayılır
            "bert_dogruluk": float(((d.bert_olumlu >= 0.5) == y).mean()),
            "sozluk_dogruluk": float(((d.sozluk >= 0) == y).mean())}


def _urun_iade_korelasyonu(veri, y):
    """Ürün başına ortalama BERT skoru ile ürünün iade oranı (finans İade / Satış, tüm dönem); Spearman + bootstrap."""
    f, _ = _birimler(veri, ("2000-01-01", "2100-01-01"))
    oran = f.groupby("model_kodu").agg(satis=("satis", "sum"), iade=("iade", "sum"))
    oran = (oran.iade / oran.satis)[oran.satis >= 30]
    u = y[y.kaynak == "urun"].groupby("model_kodu").agg(skor=("bert_olumlu", "mean"), yorum=("yorum_id", "size"))
    u = u[u.yorum >= MIN_URUN_YORUMU].join(oran.rename("iade_orani"), how="inner")
    if len(u) < 5:
        return {"urun": int(len(u)), "spearman": None}
    rng = np.random.default_rng(0)
    b = [u.iloc[rng.integers(0, len(u), len(u))].corr(method="spearman").loc["skor", "iade_orani"] for _ in range(1000)]
    return {"urun": int(len(u)), "spearman": float(u.corr(method="spearman").loc["skor", "iade_orani"]),
            "alt": float(np.nanpercentile(b, 2.5)), "ust": float(np.nanpercentile(b, 97.5))}


def degerlendir_veri(veri, y):
    e = y[y.etiket.notna()]
    fark = bootstrap_auc_farki(e.etiket.astype(int), e.bert_olumlu, e.sozluk)
    uc = y[y.puan == 3]
    return {"tum": _olcutler(e), "fark_bert_eksi_sozluk": fark,
            "kaynaga_gore": {k: _olcutler(g) for k, g in e.groupby("kaynak")},
            "uc_puan": {"n": int(len(uc)), "bert_ortalama": float(uc.bert_olumlu.mean()) if len(uc) else None,
                        "bert_olumlu_payi": float((uc.bert_olumlu >= 0.5).mean()) if len(uc) else None},
            "urun_iade_korelasyonu": _urun_iade_korelasyonu(veri, y),
            "sikayet_konulari": y[y.sikayet_iceriyor].konular.str.split(",").explode().replace("", np.nan)
            .dropna().value_counts().to_dict(),
            "sikayetli_yorum_payi_puana_gore": y.groupby("puan").sikayet_iceriyor.mean().to_dict()}


def urun_ozeti(y):
    u = y[y.kaynak == "urun"].dropna(subset=["model_kodu"])
    ozet = u.groupby("model_kodu").agg(yorum=("yorum_id", "size"), ortalama_puan=("puan", "mean"),
                                       olumlu_olasilik=("bert_olumlu", "mean"),
                                       sikayetli_yorum_payi=("sikayet_iceriyor", "mean"))
    konu = (u[u.sikayet_iceriyor].assign(k=lambda x: x.konular.str.split(",")).explode("k")
            .query("k != ''").groupby("model_kodu").k.agg(lambda x: x.value_counts().index[0]))
    return ozet.join(konu.rename("en_sik_sikayet")).reset_index().round(3)


def calistir():
    sonuc = {}
    for veri in ["sahte"] + (["gercek"] if (VERI / "gercek" / "siparisler.csv").exists() else []):
        y = skorla(veri)
        tahmin_kaydet(y.drop(columns=["yorum"]).round(4), MODEL_ID, veri)
        tahmin_kaydet(urun_ozeti(y), f"{MODEL_ID}_urun", veri)
        sonuc[veri] = degerlendir_veri(veri, y)
    if "gercek" in sonuc:
        sonuc["karar"] = sonuc["gercek"]["fark_bert_eksi_sozluk"]["alt"] > 0
    klasor = CIKTILAR / ("gercek" if "gercek" in sonuc else "sahte") / "dogrulama"
    klasor.mkdir(parents=True, exist_ok=True)
    (klasor / f"{MODEL_ID}.json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=2, default=float),
                                              encoding="utf-8")
    return sonuc


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(calistir(), ensure_ascii=False, indent=1, default=lambda x: round(float(x), 4)))
