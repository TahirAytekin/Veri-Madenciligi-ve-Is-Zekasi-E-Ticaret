"""Müşteri sorusu cevap önerici (F3-04): soru → konu, boy-kilo → beden önerisi + kalıp + stok → cevap taslağı.

    python -m tavsiye.cevap_oner --soru "165 boy 58 kilo hangi beden olur" --model esf01 --veri sahte
    python -m tavsiye.cevap_oner --degerlendir            # A: önerilen beden (gerçek satıcı cevaplarına karşı)
    python -m tavsiye.cevap_oner --degerlendir --llm      # + B: LLM taslak kalitesi (API çağrısı, ~0,01 $)

    from tavsiye.cevap_oner import cevap_oner
    sonuc = cevap_oner("165 boy 58 kilo hangi beden olur", "esf01", veri="sahte")

Kritik bilgiler kodla hesaplanır (konu, boy-kilo, önerilen beden, kalıp, stoktaki bedenler); LLM yalnızca bu bilgileri
mağazanın üslubunda cümleye döker ve yeni bilgi eklemez. API anahtarı yoksa (ya da llm=False) şablon taslak döner.
Tasarım ve başarı ölçütü: docs/modeller/F3-04.md (önceden kayıt).
"""
import argparse
import json
import re
import time

import numpy as np
import pandas as pd

from analiz import metrikler as m
from hazirlama.ortak import VERI, env_degeri, soru_konusu
from modeller import beden_uyumu as bu
from modeller.duygu_sozlugu import kucult
from modeller.ortak.degerlendir import CIKTILAR
from modeller.ortak.ozellikler import HARF_SIRASI, beden_degeri

MODEL_ID = "F3-04"
LLM_MODELI = "claude-haiku-5-5"
FIYAT = {"claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (None, None), "claude-opus-5-5": (4.0, 20.0)}  # $/MTok
EN_UZUN_CEVAP = 400
ORNEK_GERCEK, ORNEK_SAHTE = 40, 20
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
    """Sorudaki boy (cm) ve kilo; bulunamayan None. '165 boy 58 kilo', '1.65 boy 58 kg', '165/58', 'boyum 170 kilom 70'.
    """
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



# ====================================================
# 2) BİLGİLER (kodla)
# ====================================================

def _urun(veri, model_kodu):
    u = m.tablolar(veri)["urunler"]
    u = u[u.model_kodu == model_kodu]
    if u.empty:
        return None
    bedenler = sorted({b for b in u.beden.dropna()}, key=lambda b: (beden_degeri(b)[1], str(b)))
    harf = [b for b in bedenler if beden_degeri(b)[0] == "harf"]
    stokta = u[(u.stok > 0) & u.satista.fillna(False).astype(bool)].beden.dropna().unique().tolist()
    return {"ad": u.urun_adi.iloc[0], "kategori": u.kategori.iloc[0], "bedenler": bedenler, "harf_bedenler": harf,
            "stoktaki_bedenler": sorted(stokta, key=lambda b: (beden_degeri(b)[1], str(b)))}


def _en_yakin(beden, harf_bedenler):
    if not harf_bedenler or beden is None:
        return None
    hedef = HARF_SIRASI[beden]
    return min(harf_bedenler, key=lambda b: abs(beden_degeri(b)[1] - hedef))


def bilgiler(soru, model_kodu, veri="gercek", tarih=None, oneri=None):
    """LLM'e (ve şablona) verilecek doğrulanmış bilgiler. oneri: beden önerisi katsayıları (varsayılan: F2-04)."""
    tarih = pd.Timestamp(tarih) if tarih is not None else m.veri_araligi(veri)[1] + pd.Timedelta(days=1)
    k, (boy, kilo) = konu(soru), boy_kilo(soru)
    urun = _urun(veri, model_kodu)
    kalip = bu.kalip_ozellikleri(veri, [model_kodu], [tarih]).iloc[0]
    etiket = str(bu.kalip_etiketi(np.array([kalip.kalip_skoru]), np.array([kalip.beden_iadesi]))[0])
    b = {"konu": k, "boy": boy, "kilo": kilo, "urun": urun,
         "kalip": {"etiket": etiket, "kucuk_geldi_payi": round(float(kalip.kalip_skoru), 2),
                   "beden_iadesi": int(kalip.beden_iadesi)},
         "onerilen_beden": None, "setteki_en_yakin": None, "onerilen_stokta": None, "eksik": []}
    if k == "beden":
        if boy is None:
            b["eksik"].append("boy")
        if kilo is None:
            b["eksik"].append("kilo")
        if boy and kilo and urun and urun["harf_bedenler"]:
            b["onerilen_beden"] = bu.beden_oner(boy, kilo, kalip.kalip_skoru, kalip.beden_iadesi, oneri=oneri)
            b["setteki_en_yakin"] = _en_yakin(b["onerilen_beden"], urun["harf_bedenler"])
            b["onerilen_stokta"] = b["setteki_en_yakin"] in urun["stoktaki_bedenler"]
    return b


def ornek_cevaplar(veri, k, haric=None, n=3):
    """Mağazanın aynı konudaki son cevaplanmış soruları (üslup örneği)."""
    s = m.tablolar(veri)["sorular"]
    s = s[(s.konu == k) & s.cevap.notna() & (s.soru_id != haric)].sort_values("soru_tarihi").tail(n)
    return [{"soru": r.soru, "cevap": r.cevap} for r in s.itertuples()]


# ====================================================
# 3) TASLAK: LLM VEYA ŞABLON
# ====================================================

SISTEM = """Bir Trendyol mağazasının müşteri sorularına cevap taslağı yazıyorsun. Taslağı satıcı okuyup gönderecek.

Kurallar:
- Yalnızca BİLGİLER bölümündeki bilgileri kullan. Beden, stok, kalıp, kargo süresi, fiyat veya iade koşulu uydurma.
- "setteki_en_yakin" doluysa tam olarak o bedeni öner; cevapta başka hiçbir beden adı yazma. "onerilen_stokta" false
  ise bedenin şu an stokta olmadığını söyle.
- Kalıp etiketi "dar" ya da "bol" ise bunu kısaca belirt (öneri bunu zaten hesaba katıyor); "belirsiz" ise kalıptan
  hiç bahsetme.
- Beden sorusunda boy veya kilo eksikse ("eksik"), beden önerme; müşteriden boy ve kilosunu yazmasını iste.
- Bilgilerde cevabı olmayan sorularda (ölçü, kumaş, kargo tarihi gibi) bilgi uydurma; "emin_degil" alanını true yap ve
  satıcının tamamlaması için kısa, kibar bir taslak yaz. Bilgiler soruyu cevaplamaya yetiyorsa "emin_degil" false.
- En fazla 3 cümle ve 400 karakter. Mağazanın ÖRNEK CEVAPLAR'daki hitabını ve üslubunu kullan.
- Müşteriyle ilgili kişisel bilgi (isim, telefon, adres) yazma."""

SEMA = {"type": "object", "additionalProperties": False, "required": ["cevap", "emin_degil", "kullanilan_bilgiler"],
        "properties": {"cevap": {"type": "string"}, "emin_degil": {"type": "boolean"},
                       "kullanilan_bilgiler": {"type": "array", "items": {"type": "string"}}}}


def sablon_cevap(b):
    """LLM olmadan, aynı bilgilerden kısa taslak (mağazanın sık kullandığı kalıpla)."""
    bas = "Değerli Müşterimiz, "
    if b["konu"] == "beden":
        if b["eksik"]:
            return bas + "size doğru bedeni önerebilmemiz için boy ve kilo bilginizi yazar mısınız? 🙏"
        if b["setteki_en_yakin"]:
            beden = b["setteki_en_yakin"]
            metin = bas + f"verdiğiniz bilgilere göre sizin için {beden} beden uygundur"
            if b["kalip"]["etiket"] in ("dar", "bol"):
                metin += f" (ürünün kalıbı {b['kalip']['etiket']}, öneri buna göre)"
            metin += "." if b["onerilen_stokta"] else ", ancak bu beden şu an stoklarımızda yok."
            return metin + " Keyifli alışverişler dileriz 🙏"
    return bas + "sorunuz için teşekkür ederiz; en kısa sürede bilgi vereceğiz 🙏"


def _istemci():
    anahtar = env_degeri("ANTHROPIC_API_KEY")
    if not anahtar:
        return None
    import anthropic
    return anthropic.Anthropic(api_key=anahtar)


def llm_cevap(soru, b, ornekler, istemci, model=LLM_MODELI):
    """(çıktı sözlüğü, kullanım). Yapılandırılmış çıktı; reddedilirse veya biçim bozuksa None döner."""
    icerik = ("BİLGİLER:\n" + json.dumps(b, ensure_ascii=False, default=str) + "\n\nÖRNEK CEVAPLAR:\n"
              + json.dumps(ornekler, ensure_ascii=False) + "\n\nMÜŞTERİ SORUSU:\n" + str(soru))
    yanit = istemci.messages.create(
        model=model, max_tokens=1024,
        system=[{"type": "text", "text": SISTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": icerik}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SEMA}})
    kullanim = {"girdi": yanit.usage.input_tokens, "cikti": yanit.usage.output_tokens,
                "onbellek_okuma": getattr(yanit.usage, "cache_read_input_tokens", 0) or 0}
    if yanit.stop_reason in ("refusal", "max_tokens"):
        return None, kullanim
    metin = next((x.text for x in yanit.content if x.type == "text"), None)
    try:
        cikti = json.loads(metin)
    except (TypeError, json.JSONDecodeError):
        return None, kullanim
    return cikti, kullanim


def maliyet(kullanim, model=LLM_MODELI):
    girdi, cikti = FIYAT.get(model, (None, None))
    if girdi is None:
        return None
    return (kullanim["girdi"] * girdi + kullanim["cikti"] * cikti) / 1e6


def cevap_oner(soru, model_kodu, veri="gercek", tarih=None, llm=True, soru_id=None, istemci=None, oneri=None):
    b = bilgiler(soru, model_kodu, veri, tarih, oneri)
    sonuc = {"soru": soru, "model_kodu": model_kodu, "bilgiler": b, "kaynak": "sablon", "cevap": sablon_cevap(b),
             "emin_degil": b["konu"] != "beden" or bool(b["eksik"]), "kullanim": None, "maliyet_usd": None}
    istemci = istemci or (_istemci() if llm else None)
    if istemci is not None:
        cikti, kullanim = llm_cevap(soru, b, ornek_cevaplar(veri, b["konu"], soru_id), istemci)
        sonuc.update(kullanim=kullanim, maliyet_usd=maliyet(kullanim))
        if cikti is not None and beden_dogru_mu(cikti["cevap"], b):
            sonuc.update(kaynak="llm", cevap=cikti["cevap"], emin_degil=cikti["emin_degil"],
                         kullanilan_bilgiler=cikti["kullanilan_bilgiler"])
        elif cikti is not None:
            sonuc["kaynak"] = "sablon_llm_reddedildi"
    return sonuc


def beden_dogru_mu(cevap, b):
    """Güvenlik kontrolü (F3-04 değerlendirmesinden SONRA eklendi): öneri varsa LLM cevabında yalnızca o beden geçmeli.
    Geçmezse taslak şablona döner; kritik bilgi (beden) hiçbir zaman LLM'e bırakılmaz."""
    hedef = b["setteki_en_yakin"]
    return hedef is None or set(cevaptaki_bedenler(cevap)) == {hedef}


# ====================================================
# 4) DEĞERLENDİRME (docs/modeller/F3-04.md)
# ====================================================

def beden_test_kumesi(veri):
    """Boy ve kilo yazılmış, satıcının tek harf bedenle cevapladığı, harf bedenli ürünlere ait beden soruları."""
    t = m.tablolar(veri)
    harf_model = set(t["urunler"][[beden_degeri(x)[0] == "harf" for x in t["urunler"].beden]].model_kodu)
    s = t["sorular"]
    s = s[(s.konu == "beden") & s.model_kodu.isin(harf_model)].copy()
    s[["boy", "kilo"]] = s.soru.map(boy_kilo).tolist()
    s["satici_bedenleri"] = s.cevap.map(cevaptaki_bedenler)
    s = s[s.boy.notna() & s.kilo.notna() & (s.satici_bedenleri.str.len() == 1)].reset_index(drop=True)
    s["satici_degeri"] = s.satici_bedenleri.map(lambda x: float(HARF_SIRASI[x[0]]))
    return s.join(bu.kalip_ozellikleri(veri, s.model_kodu, s.soru_tarihi))


def _a_olc(test, oneri, en_sik):
    duzelt = oneri.get("kalip_duzeltmesi")
    p = bu._oneri_degeri(oneri, test.boy, test.kilo, test.kalip_skoru if duzelt else None,
                         test.beden_iadesi if duzelt else None)
    y = test.satici_degeri.to_numpy()
    fark = bu._isabet_farki(p == y, np.full(len(y), en_sik) == y)
    return {"n": int(len(y)), "tam_isabet": float((p == y).mean()), "bir_beden_isabet": float((abs(p - y) <= 1).mean()),
            "en_sik_isabet": float((en_sik == y).mean()), "en_sik_beden": bu.HARF_ADI[int(en_sik)],
            "ortalama_fark_oneri_eksi_satici": float((p - y).mean()), "fark_en_sik": fark,
            "kalip_duzeltmesi": bool(duzelt)}


def degerlendir_a():
    gercek = beden_test_kumesi("gercek") if (VERI / "gercek" / "siparisler.csv").exists() else None
    sonuc = {"gercek": {}, "seviye1": {}}
    for tohum, veri in bu.SAHTE_TOHUMLAR.items():
        if not (VERI / veri / "siparisler.csv").exists():
            continue
        oneri = bu.oneri_egit(veri)
        s1 = bu.seviye1_duzeltme(veri, oneri)
        oneri["kalip_duzeltmesi"] = s1["duzeltmeli"] > s1["duzeltmesiz"]       # F2-04 ile aynı seçim (yalnızca sahte)
        sahte_test = beden_test_kumesi(veri)
        en_sik = float(sahte_test.satici_degeri.mode()[0])                    # sahte satıcının en sık önerisi
        sonuc["seviye1"][tohum] = _a_olc(sahte_test, oneri, en_sik)
        if gercek is not None:
            sonuc["gercek"][tohum] = _a_olc(gercek, oneri, en_sik)
    if sonuc["gercek"]:
        sonuc["karar_A"] = sum(v["fark_en_sik"]["alt"] > 0 for v in sonuc["gercek"].values()) >= 2
    return sonuc


def _kontroller(s):
    b, cevap = s["bilgiler"], str(s["cevap"])
    bedenler = set(cevaptaki_bedenler(cevap))
    set_harf = set(b["urun"]["harf_bedenler"]) if b["urun"] else set()
    k = {"sema": s["kaynak"] == "llm", "uzunluk": len(cevap) <= EN_UZUN_CEVAP,
         "set_disi_beden_yok": not (bedenler - set_harf) if set_harf else not bedenler}
    hedef = b["setteki_en_yakin"]
    if hedef:
        k["onerilen_beden"] = bedenler == {hedef}
    elif b["konu"] == "beden" and b["eksik"]:
        k["eksik_bilgi_isteniyor"] = bool(re.search(r"boy|kilo", kucult(cevap))) or bool(s["emin_degil"])
    return k


def degerlendir_b(veri, n, tohum=0):
    s = m.tablolar(veri)["sorular"].dropna(subset=["model_kodu"])
    ornek = s.sample(min(n, len(s)), random_state=tohum)
    istemci = _istemci()
    if istemci is None:
        return {"hata": "ANTHROPIC_API_KEY yok"}
    satirlar, toplam, sure = [], {"girdi": 0, "cikti": 0, "onbellek_okuma": 0}, time.time()
    for r in ornek.itertuples():
        x = cevap_oner(r.soru, r.model_kodu, veri, r.soru_tarihi, soru_id=r.soru_id, istemci=istemci)
        x["kontroller"] = _kontroller(x)
        satirlar.append(x)
        for a in toplam:
            toplam[a] += (x["kullanim"] or {}).get(a, 0)
    kontrol = pd.DataFrame([x["kontroller"] for x in satirlar]).astype(float)   # her soruda olmayan kontrol: NaN
    return {"n": len(satirlar), "gecme_orani": kontrol.mean().round(4).to_dict(),
            "kontrol_sayisi": kontrol.notna().sum().to_dict(), "kullanim": toplam,
            "maliyet_usd": maliyet(toplam), "sure_sn": round(time.time() - sure, 1),
            "konular": pd.Series([x["bilgiler"]["konu"] for x in satirlar]).value_counts().to_dict(),
            "ornekler": [{k: x[k] for k in ("soru", "cevap", "kaynak", "emin_degil", "kontroller")}
                         | {"onerilen": x["bilgiler"]["setteki_en_yakin"]} for x in satirlar]}


def calistir(llm=False):
    sonuc = {"A": degerlendir_a()}
    if llm:
        sonuc["B"] = {v: degerlendir_b(v, n) for v, n in [("gercek", ORNEK_GERCEK), ("sahte", ORNEK_SAHTE)]
                      if (VERI / v / "siparisler.csv").exists()}
        g = sonuc["B"].get("gercek", {})
        if "gecme_orani" in g:
            sonuc["karar_B"] = all(v >= 0.9 for v in g["gecme_orani"].values())
    klasor = CIKTILAR / ("gercek" if (VERI / "gercek" / "siparisler.csv").exists() else "sahte") / "dogrulama"
    klasor.mkdir(parents=True, exist_ok=True)
    (klasor / f"{MODEL_ID}.json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=2, default=str),
                                              encoding="utf-8")
    return sonuc


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--soru")
    p.add_argument("--model", help="model_kodu")
    p.add_argument("--veri", default="sahte", choices=["sahte", "gercek"])
    p.add_argument("--sablon", action="store_true", help="LLM kullanma")
    p.add_argument("--degerlendir", action="store_true")
    p.add_argument("--llm", action="store_true", help="değerlendirmede B (LLM) bölümünü de çalıştır")
    a = p.parse_args()
    if a.degerlendir:
        r = calistir(llm=a.llm)
        for v in r.get("B", {}).values():
            v.pop("ornekler", None)
        print(json.dumps(r, ensure_ascii=False, indent=1, default=str))
    else:
        print(json.dumps(cevap_oner(a.soru, a.model, a.veri, llm=not a.sablon), ensure_ascii=False, indent=1,
                         default=str))
