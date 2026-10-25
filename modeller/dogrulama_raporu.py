"""Doğrulama raporu (F2-12): tüm modellerin sahte → gerçek sonuçları tek tabloda. Web'deki "Model Doğrulama" sayfası
buradan okur.

    python -m modeller.dogrulama_raporu              # mevcut ciktilar/ sonuçlarından raporu üretir
    python -m modeller.dogrulama_raporu --yeniden    # önce tüm modelleri sırayla yeniden çalıştırır (~3 dk)

Girdi: ciktilar/<veri>/dogrulama/F2-0*.json, ciktilar/modeller/*_ozet.json, F1-06_surum_karsilastirma.json
Çıktı:
    docs/rapor/02_dogrulama.md      okunur rapor (git'e girer; "Yorum" bölümü elle yazılır ve korunur)
    docs/rapor/02_dogrulama.json    web için tablo (git'e girer: yalnızca toplu ölçütler, kişisel/ticari satır yok)
    ciktilar/gercek/dogrulama.json  aynı tablo (plan çıktısı)
Gerçek veri yoksa (ekip üyeleri) rapor üretilmez; depodaki 02_dogrulama.json kullanılır.
"""
import json
import subprocess
import sys

from hazirlama.ortak import PROJE, VERI
from modeller.ortak.degerlendir import CIKTILAR

RAPOR = PROJE / "docs" / "rapor" / "02_dogrulama.md"
RAPOR_JSON = PROJE / "docs" / "rapor" / "02_dogrulama.json"
YORUM_BAS, YORUM_SON = "<!-- YORUM -->", "<!-- /YORUM -->"
SIRA = ["modeller.iade_riski", "modeller.iade_riski_mlp", "modeller.surum_karsilastirma", "modeller.beden_uyumu",
        "modeller.talep", "modeller.duygu"]


# ====================================================
# 1) OKUMA
# ====================================================

def _oku(*parcalar):
    yol = CIKTILAR.joinpath(*parcalar)
    return json.loads(yol.read_text(encoding="utf-8")) if yol.exists() else None


def _olcut(d, skor, alan="roc_auc"):
    return next(r[alan] for r in d["olcutler"] if r["skor"] == skor)


def _satir(id_, ad, soru, yontem, metrik, yon, model, referans_adi, referans, fark, karar, web, kart,
           seviye1=None, tohumlar=None, not_=""):
    return {"id": id_, "ad": ad, "soru": soru, "yontem": yontem, "metrik": metrik, "yon": yon,
            "gercek_model": model, "referans_adi": referans_adi, "gercek_referans": referans,
            "fark": fark.get("ortalama", fark.get("fark")), "alt": fark["alt"], "ust": fark["ust"],
            "karar": "basarili" if karar else "basarisiz", "seviye1": seviye1 or {}, "tohumlar": tohumlar or {},
            "not": not_, "web": web, "kart": kart}


# ====================================================
# 2) MODEL BAŞINA SATIRLAR
# ====================================================

def f202():
    g, s, oz = _oku("gercek", "dogrulama", "F2-02.json"), _oku("sahte", "dogrulama", "F2-02.json"), \
        _oku("modeller", "F2-02_ozet.json")
    surum = _oku("modeller", "F1-06_surum_karsilastirma.json")
    fark = oz["ek_olcutler"]["gercek"]["auc_farki_model_eksi_urun_gecmisi"]
    tohumlar = {str(r["tohum"]): {"model": r["gercek_auc"], "fark": r["fark_urun_gecmisi"], "alt": r["fark_alt"],
                                  "ust": r["fark_ust"]} for r in surum["tablo"] if r["surum"] == "v2"} if surum else {}
    return _satir("F2-02", "İade riski (GBM)", "Bu sipariş satırı iade edilecek mi?", "LightGBM, monoton kısıt adayı",
                  "ROC-AUC", "yuksek_iyi", _olcut(g, "model"), "ürün geçmiş iade oranı",
                  _olcut(g, "baseline_model_gecmisi"), fark, fark["alt"] > 0,
                  "Ürün düzeyinde risk ürün geçmişinden; model yeni (geçmişi az) ürünlerde yedek",
                  "docs/modeller/F2-02.md",
                  seviye1={"model": _olcut(s, "model"), "referans": _olcut(s, "baseline_model_gecmisi"),
                           "kahin": _olcut(s, "kahin_ust_sinir")}, tohumlar=tohumlar,
                  not_=f"seçilen varyant: {oz['secilen_varyant']}")


def f203():
    g, s, oz = _oku("gercek", "dogrulama", "F2-03.json"), _oku("sahte", "dogrulama", "F2-03.json"), \
        _oku("modeller", "F2-03_ozet.json")
    e = oz["ek_olcutler"]["gercek"]
    return _satir("F2-03", "İade riski (derin öğrenme)", "Bu sipariş satırı iade edilecek mi?",
                  "PyTorch MLP, kategorik gömme, 5 tohumlu topluluk", "ROC-AUC", "yuksek_iyi", _olcut(g, "model"),
                  "ürün geçmiş iade oranı", _olcut(g, "baseline_model_gecmisi"), e["auc_farki_model_eksi_urun_gecmisi"],
                  e["auc_farki_model_eksi_urun_gecmisi"]["alt"] > 0, "Kullanılmaz (F2-02 daha iyi); karşılaştırma için",
                  "docs/modeller/F2-03.md",
                  seviye1={"model": _olcut(s, "model"), "referans": _olcut(s, "baseline_model_gecmisi"),
                           "kahin": _olcut(s, "kahin_ust_sinir")},
                  not_=f"seçilen varyant: {oz['secilen_varyant']}; F2-02'ye göre fark "
                       f"{e['auc_farki_model_eksi_f202']['ortalama']:+.3f} "
                       f"[{e['auc_farki_model_eksi_f202']['alt']:+.3f}, {e['auc_farki_model_eksi_f202']['ust']:+.3f}]")


def f204():
    d = _oku("gercek", "dogrulama", "F2-04.json")
    a = d["A"]
    satirlar = [_satir("F2-04A", "Kalıp skoru", "Beden iadesi küçük mü büyük mü gelecek? (ürün kalıbından)",
                       "Eğitimsiz: Beta yumuşatmalı küçük geldi payı", "ROC-AUC", "yuksek_iyi", a["auc"],
                       "sabit tahmin", 0.5, {"ortalama": a["auc"] - 0.5, "alt": a["alt"] - 0.5, "ust": a["ust"] - 0.5},
                       d["karar"]["A"], "Kalıbı dar/bol ürün tavsiyesi, kanıt sayısıyla", "docs/modeller/F2-04.md",
                       seviye1={"model": d["seviye1"]["42"]["kalip"]["dar_auc"]},
                       not_="Seviye 1: gizli dar kalıbı ayırt etme AUC'si")]

    def tohum(alan, ic, deger, ref):
        return {t: {"model": v[deger], "referans": v.get(ref) if ref else None, "fark": v[ic][alan[0]],
                    "alt": v[ic]["alt"], "ust": v[ic]["ust"]} for t, v in d[alan[1]].items()}
    b = tohum(("ortalama", "B"), "fark_kalip_skoru", "auc", None)
    b42 = d["B"]["42"]
    satirlar.append(_satir("F2-04B", "Beden iadesi yönü", "Beden iadesi küçük mü büyük mü gelecek? (satır düzeyi)",
                           "LightGBM, kalıp skorunda monoton", "ROC-AUC", "yuksek_iyi", b42["auc"], "kalıp skoru",
                           b42["auc"] - b42["fark_kalip_skoru"]["ortalama"], b42["fark_kalip_skoru"], d["karar"]["B"],
                           "Kullanılmaz", "docs/modeller/F2-04.md", tohumlar=b,
                           seviye1={"model": d["seviye1"]["42"]["yon_sahte_dogrulama"]["model"],
                                    "referans": d["seviye1"]["42"]["yon_sahte_dogrulama"]["kalip_skoru"]}))
    c = tohum(("fark", "C"), "fark_en_sik", "tam_isabet", "en_sik_isabet")
    c42 = d["C"]["42"]
    satirlar.append(_satir("F2-04C", "Beden önerisi", "Boyu ve kilosu bilinen müşteriye hangi beden?",
                           "Doğrusal regresyon (boy, kilo) + kalıp düzeltmesi", "tam isabet", "yuksek_iyi",
                           c42["tam_isabet"], "en sık beden", c42["en_sik_isabet"], c42["fark_en_sik"], d["karar"]["C"],
                           "Beden önerici (müşteri boy-kilo girer)", "docs/modeller/F2-04.md", tohumlar=c,
                           seviye1={"model": d["seviye1"]["42"]["oneri"]["tam_isabet"],
                                    "referans": d["seviye1"]["42"]["oneri"]["en_sik_isabet"]},
                           not_=f"±1 beden isabeti {c42['bir_beden_isabet']:.3f}; {c42['n']} gerçek yorum"))
    return satirlar


def f205():
    d = _oku("gercek", "dogrulama", "F2-05.json")
    g, s = d["gercek"]["42"], d["seviye1"]["42"]
    ref = g["en_iyi_referans"]
    tohumlar = {t: {"model": v["wape"], "referans": v[f"wape_{v['en_iyi_referans']}"],
                    "fark": v["fark_en_iyi_referans"]["fark"], "alt": v["fark_en_iyi_referans"]["alt"],
                    "ust": v["fark_en_iyi_referans"]["ust"]} for t, v in d["gercek"].items()}
    return _satir("F2-05", "Haftalık talep", "Bu ürün gelecek hafta kaç adet satar?", "LightGBM (Poisson)", "WAPE",
                  "dusuk_iyi", g["wape"], {"naif": "geçen haftanın satışı", "ort4": "son 4 hafta ortalaması"}[ref],
                  g[f"wape_{ref}"], g["fark_en_iyi_referans"], d["karar"],
                  "Kullanılmaz; stok tükenme tablosu geçen haftanın satış hızıyla", "docs/modeller/F2-05.md",
                  seviye1={"model": s["wape"], "referans": min(s["wape_naif"], s["wape_ort4"]),
                           "kahin": s["kahin_wape"]},
                  tohumlar=tohumlar,
                  not_=f"mağaza toplamı WAPE: model {g['magaza_wape']:.3f}, naif {g['magaza_wape_naif']:.3f}")


def f206():
    d = _oku("gercek", "dogrulama", "F2-06.json")
    g, s = d["gercek"]["tum"], d["sahte"]["tum"]
    return _satir("F2-06", "Yorum duygusu (BERT)", "Bu yorum olumlu mu olumsuz mu?",
                  "Hazır Türkçe BERT, sıfır atış", "ROC-AUC", "yuksek_iyi", g["bert_auc"], "kelime listesi",
                  g["sozluk_auc"], d["gercek"]["fark_bert_eksi_sozluk"], d["karar"],
                  "Şikâyet işareti ve şikâyet konusu (genel duygu puandan)", "docs/modeller/F2-06.md",
                  seviye1={"model": s["bert_auc"], "referans": s["sozluk_auc"]},
                  not_=f"{g['n']} gerçek yorum ({g['olumsuz']} olumsuz); ürün yorumlarında BERT "
                       f"{d['gercek']['kaynaga_gore']['urun']['bert_auc']:.3f}, sözlük "
                       f"{d['gercek']['kaynaga_gore']['urun']['sozluk_auc']:.3f}")


def f304():
    d = _oku("gercek", "dogrulama", "F3-04.json")
    if d is None:
        return []
    a, s1 = d["A"]["gercek"], d["A"]["seviye1"]
    g = a["42"]
    tohumlar = {t: {"model": v["tam_isabet"], "referans": v["en_sik_isabet"], "fark": v["fark_en_sik"]["fark"],
                    "alt": v["fark_en_sik"]["alt"], "ust": v["fark_en_sik"]["ust"]} for t, v in a.items()}
    b = d.get("B", {}).get("gercek", {})
    return [_satir("F3-04", "Soru cevabında beden önerisi", "Boyunu ve kilosunu yazan müşteriye satıcı hangi bedeni "
                   "önerir?", "beden_oner() + kalıp düzeltmesi; LLM (Haiku 5.5) yalnızca metni yazar", "tam isabet",
                   "yuksek_iyi", g["tam_isabet"], f"en sık beden ({g['en_sik_beden']})", g["en_sik_isabet"],
                   g["fark_en_sik"], d["A"]["karar_A"], "Soru cevap önerici (taslak; beden kodla belirlenir)",
                   "docs/modeller/F3-04.md", seviye1={"model": s1["42"]["tam_isabet"],
                                                      "referans": s1["42"]["en_sik_isabet"]}, tohumlar=tohumlar,
                   not_=f"{g['n']} gerçek satıcı cevabı; ±1 beden isabeti {g['bir_beden_isabet']:.3f}. LLM taslak "
                        f"kontrolü (B): önerilen bedeni yazma oranı "
                        f"{b.get('gecme_orani', {}).get('onerilen_beden', float('nan')):.3f} (ölçüt ≥ 0,90, tutmadı); "
                        "sonradan eklenen güvenlik kontrolü yanlış bedenli taslağı şablona çevirir.")]


def tablo():
    satirlar = []
    for f in (f202, f203, f204, f205, f206, f304):
        sonuc = f()
        satirlar.extend(sonuc if isinstance(sonuc, list) else [sonuc])
    surum = _oku("modeller", "F1-06_surum_karsilastirma.json")
    return {"satirlar": satirlar, "sahte_v1_v2": surum["tablo"] if surum else None,
            "test_donemi": _oku("gercek", "dogrulama", "F2-02.json")["test_donemi"]}


# ====================================================
# 3) RAPOR
# ====================================================

def _s(x, n=3, isaret=False):
    if x is None:
        return "—"
    return (f"{x:+.{n}f}" if isaret else f"{x:.{n}f}").replace(".", ",")


def markdown(t, yorum):
    r = t["satirlar"]
    basarili = [x["id"] for x in r if x["karar"] == "basarili"]
    satir = ["# Model doğrulama raporu (F2-12)", "",
             "> Bu dosya `python -m modeller.dogrulama_raporu` ile üretilir; elle değiştirmeyin. Yalnızca "
             "\"Yorum\" bölümü elle yazılır ve yeniden üretimde korunur. Web için tablo: `02_dogrulama.json`.", "",
             "## Yöntem (tüm modellerde aynı)",
             "- **Eğitim yalnızca sahte veriyle** (sahte v2, [F1-06](sahte_v2_kalibrasyon.md)); gerçek veri yalnızca "
             f"test. Gerçek test dönemi: {t['test_donemi']['baslangic']} – {t['test_donemi']['bitis']} siparişleri "
             "(talep ve duygu için kendi pencereleri, bkz. kartlar).",
             "- **Önceden kayıt:** her modelin tasarımı ve başarı ölçütü eğitimden önce commitlendi; sonradan "
             "değiştirilmedi. Gerçek sonuç görüldükten sonra yapılan denemeler kartlarda \"keşifsel\" etiketli.",
             "- **Referans:** her model, eğitim gerektirmeyen en güçlü basit yöntemle karşılaştırılır. **Başarı:** "
             "farkın %95 bootstrap güven aralığı 0'ın doğru tarafında. 3 sahte tohumlu modellerde en az 2 tohumda.",
             "- **Seviye 1:** sahte veride gizli doğru cevapla (kâhin) karşılaştırma.", "",
             "## Sonuç tablosu (gerçek test)", "",
             "| görev | soru | ölçüt | model | referans | fark [%95 GA] | tohumlarda | karar | web'de |",
             "|---|---|---|---|---|---|---|---|---|"]
    for x in r:
        if x["tohumlar"]:
            iyi = sum((v["alt"] > 0) if x["yon"] == "yuksek_iyi" else (v["ust"] < 0) for v in x["tohumlar"].values())
            tohum = f"{iyi}/{len(x['tohumlar'])}"
        else:
            tohum = "—"
        satir.append(f"| [{x['id']}](../../{x['kart']}) | {x['soru']} | {x['metrik']} | {_s(x['gercek_model'])} | "
                     f"{x['referans_adi']}: {_s(x['gercek_referans'])} | {_s(x['fark'], isaret=True)} "
                     f"[{_s(x['alt'], isaret=True)}, {_s(x['ust'], isaret=True)}] | {tohum} | "
                     f"{'✓' if x['karar'] == 'basarili' else '✗'} | {x['web']} |")
    satir += ["", f"**Başarılı:** {', '.join(basarili) or 'yok'} · **Başarısız:** "
              f"{', '.join(x['id'] for x in r if x['karar'] != 'basarili')}", "",
              "WAPE'de düşük değer iyidir (fark < 0 model lehine); diğer ölçütlerde yüksek değer iyidir.", "",
              "## Seviye 1 (sahte veri, gizli doğru cevap)", "",
              "| görev | model | referans | kâhin (tavan / taban) |", "|---|---|---|---|"]
    for x in r:
        s1 = x["seviye1"]
        if s1:
            satir.append(f"| {x['id']} | {_s(s1.get('model'))} | {_s(s1.get('referans'))} | {_s(s1.get('kahin'))} |")
    satir += ["", "## Tohumlara göre (sahte v2: 42, 1, 2)", "",
              "| görev | tohum | model | fark [%95 GA] |", "|---|---|---|---|"]
    for x in r:
        for tohum, v in x["tohumlar"].items():
            satir.append(f"| {x['id']} | {tohum} | {_s(v['model'])} | {_s(v['fark'], isaret=True)} "
                         f"[{_s(v['alt'], isaret=True)}, {_s(v['ust'], isaret=True)}] |")
    if t["sahte_v1_v2"]:
        satir += ["", "## Sahte veri v1 → v2 (F2-02, gerçek AUC)", "", "| sürüm | tohum | seçilen | gerçek AUC | "
                  "− ürün geçmişi [%95 GA] |", "|---|---|---|---|---|"]
        for v in t["sahte_v1_v2"]:
            satir.append(f"| {v['surum']} | {v['tohum']} | {v['secilen']} | {_s(v['gercek_auc'])} | "
                         f"{_s(v['fark_urun_gecmisi'], isaret=True)} [{_s(v['fark_alt'], isaret=True)}, "
                         f"{_s(v['fark_ust'], isaret=True)}] |")
    satir += ["", "## Notlar", ""] + [f"- **{x['id']}:** {x['not']}" for x in r if x["not"]]
    satir += ["", "## Yorum", "", YORUM_BAS, yorum.strip(), YORUM_SON, ""]
    return "\n".join(satir)


def _mevcut_yorum():
    if RAPOR.exists():
        metin = RAPOR.read_text(encoding="utf-8")
        if YORUM_BAS in metin and YORUM_SON in metin:
            return metin.split(YORUM_BAS)[1].split(YORUM_SON)[0]
    return "_(elle yazılacak)_"


def calistir(yeniden=False):
    if not (VERI / "gercek" / "siparisler.csv").exists():
        print("Gerçek veri yok: rapor üretilmedi. Depodaki docs/rapor/02_dogrulama.json kullanılır.")
        return None
    if yeniden:
        for modul in SIRA:
            print(f"çalışıyor: {modul}", flush=True)
            subprocess.run([sys.executable, "-m", modul], cwd=PROJE, check=True, capture_output=True)
    t = tablo()
    metin = json.dumps(t, ensure_ascii=False, indent=2, default=float)
    RAPOR_JSON.write_text(metin + "\n", encoding="utf-8")
    (CIKTILAR / "gercek").mkdir(parents=True, exist_ok=True)
    (CIKTILAR / "gercek" / "dogrulama.json").write_text(metin, encoding="utf-8")
    RAPOR.write_text(markdown(t, _mevcut_yorum()), encoding="utf-8")
    return t


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    t = calistir(yeniden="--yeniden" in sys.argv)
    if t:
        for x in t["satirlar"]:
            print(f"{x['id']:7s} {x['karar']:10s} model {x['gercek_model']:.3f} | {x['referans_adi']} "
                  f"{x['gercek_referans']:.3f} | fark {x['fark']:+.3f} [{x['alt']:+.3f}, {x['ust']:+.3f}]")
