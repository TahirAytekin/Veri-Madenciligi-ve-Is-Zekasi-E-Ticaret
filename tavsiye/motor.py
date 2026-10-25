"""Tavsiye motoru ve haftalık aksiyon planı (F3-03).

    python -m tavsiye.motor --veri sahte
    python -m tavsiye.motor --veri gercek

Tüm kuralları çalıştırır, tavsiyeleri önceliklendirir ve haftalık planı çıkarır:
    öncelik = beklenen aylık etki (TL) × güven puanı      (etkisi ölçülebilenler)
    plan    = ilk PLAN_TL ölçülebilir + ilk PLAN_DIGER ölçülemeyen (önem, sonra güven sırasıyla)
Planın toplam kazancı üst sınırdır: bazı tavsiyelerin etkileri örtüşür (ör. kalıp notu ve beden önerici).

Çıktılar (ciktilar/, git'e girmez):
    <veri>/tavsiyeler.json      tüm tavsiyeler + çalışmayan kurallar
    <veri>/aksiyon_plani.json   haftalık plan (ilk 10)
Model çıktılarına dayanan kurallar için önce: python -m modeller.dogrulama_raporu --yeniden (veya ilgili modeller).
"""
import argparse
import json
import traceback

from analiz import metrikler as m
from hazirlama.ortak import VERI
from modeller.ortak.degerlendir import CIKTILAR
from tavsiye.kurallar import ESIK, KURALLAR, VARSAYIM, Baglam
from tavsiye.sema import GUVEN_PUANI, ONEM_SIRASI

PLAN_TL, PLAN_DIGER = 7, 3


def tavsiyeler(veri="sahte"):
    """(tavsiye listesi, hata listesi). Bir kural hata verirse diğerleri çalışmaya devam eder."""
    b = Baglam(veri)
    sonuc, hatalar = [], []
    for kural in KURALLAR:
        try:
            sonuc.extend(kural(b))
        except Exception as e:                       # noqa: BLE001 — kural hatası raporlanır, motor durmaz
            hatalar.append({"kural": kural.__name__, "hata": f"{type(e).__name__}: {e}",
                            "iz": traceback.format_exc(limit=3)})
    return sirala(sonuc), hatalar, b


def sirala(liste):
    olculen = sorted([t for t in liste if t.etki_tl is not None], key=lambda t: -t.oncelik)
    diger = sorted([t for t in liste if t.etki_tl is None],
                   key=lambda t: (ONEM_SIRASI[t.onem], -GUVEN_PUANI[t.guven]))
    return olculen + diger


def aksiyon_plani(liste):
    olculen = [t for t in liste if t.etki_tl is not None and t.etki_tl > 0][:PLAN_TL]
    diger = [t for t in liste if t.etki_tl is None][:PLAN_DIGER]
    plan = olculen + diger
    return {"aksiyonlar": [{"sira": i + 1, **t.sozluk()} for i, t in enumerate(plan)],
            "toplam_aylik_etki_tl": sum(t.etki_tl for t in olculen),
            "agirlikli_toplam_tl": sum(t.oncelik for t in olculen),
            "not": "Toplam üst sınırdır: bazı tavsiyelerin etkileri örtüşür. Etkiler aylık katkı payı farkıdır "
                   "(ürün maliyeti hariç)."}


def calistir(veri="sahte"):
    liste, hatalar, b = tavsiyeler(veri)
    plan = aksiyon_plani(liste)
    ortak = {"veri": veri, "donem": b.donem(), "varsayimlar": VARSAYIM, "esikler": ESIK}
    klasor = CIKTILAR / veri
    klasor.mkdir(parents=True, exist_ok=True)
    (klasor / "tavsiyeler.json").write_text(json.dumps(
        {**ortak, "tavsiyeler": [t.sozluk() for t in liste], "hatalar": hatalar,
         "tur_sayilari": _say(liste)}, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    (klasor / "aksiyon_plani.json").write_text(json.dumps({**ortak, **plan}, ensure_ascii=False, indent=2,
                                                          default=float), encoding="utf-8")
    return liste, plan, hatalar


def _say(liste):
    s = {}
    for t in liste:
        s[t.tur] = s.get(t.tur, 0) + 1
    return s


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--veri", default="sahte", choices=["sahte", "gercek"])
    a = p.parse_args()
    if not (VERI / a.veri / "siparisler.csv").exists():
        sys.exit(f"veri yok: {a.veri}")
    m.yenile()
    liste, plan, hatalar = calistir(a.veri)
    print(f"{len(liste)} tavsiye · türler: {_say(liste)}")
    for h in hatalar:
        print(f"HATA {h['kural']}: {h['hata']}")
    print(f"\nHaftalık aksiyon planı (aylık toplam etki üst sınırı: {plan['toplam_aylik_etki_tl']:,.0f} TL):")
    for x in plan["aksiyonlar"]:
        etki = f"{x['etki_tl']:>9,.0f} TL" if x["etki_tl"] is not None else "        — "
        print(f"{x['sira']:2d}. [{x['guven']:6s}] {etki}  {x['baslik']}\n      → {x['aksiyon']}")
