"""Haftalık PDF rapor (geliştirme turu, adım 5): bu haftanın göstergeleri, aksiyon planı, dikkat edilecekler.

    python -m tavsiye.haftalik_rapor --veri gercek        # ciktilar/<veri>/haftalik_rapor_<bitiş>.pdf

    from tavsiye.haftalik_rapor import pdf_uret
    icerik = pdf_uret("sahte")                            # bytes (panelde indirme düğmesi)

Rapor hesap yapmaz: metrikler (analiz/metrikler.py), durum raporu, tavsiye motoru, ürün kartları ve model çıktılarından
okur. Yazı tipi matplotlib'in içindeki DejaVu Sans (Türkçe karakterler her işletim sisteminde aynı görünür).
"""
import argparse
import io
import json
import re
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from fpdf import FPDF  # noqa: E402

from analiz import metrikler as m  # noqa: E402
from analiz.durum import sayi, tl, yuzde  # noqa: E402
from hazirlama.ortak import PROJE  # noqa: E402
from modeller.ortak.degerlendir import CIKTILAR  # noqa: E402

YAZI_TIPI = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
VURGU, GRI, KOYU = (42, 120, 214), (110, 110, 110), (30, 30, 30)
VERI_ADI = {"gercek": "Gerçek mağaza", "sahte": "Sahte (demo) mağaza"}
HAFTALIK = [("ciro_net", "Net satış"), ("siparis_sayisi", "Sipariş sayısı"), ("satilan_adet", "Satılan adet"),
            ("ortalama_sepet", "Ortalama sepet"), ("katki_payi", "Katkı payı"), ("katki_marji", "Katkı marjı"),
            ("iptal_orani", "İptal oranı"), ("medyan_cevap_suresi_dk", "Soru cevap süresi (medyan)")]
GUVEN = {"yuksek": "yüksek", "orta": "orta", "dusuk": "düşük"}
KONU_ADI = {"beden_kalip": "beden/kalıp", "kumas_kalite": "kumaş/kalite", "kargo_paket": "kargo/paket",
            "renk_gorsel": "renk/görsel", "urun_hatasi": "ürün hatası", "fiyat": "fiyat"}


# ====================================================
# 1) VERİ
# ====================================================

def _bicim(deger, birim):
    if deger is None or pd.isna(deger):
        return "—"
    return {"TL": tl, "oran": lambda x: yuzde(x), "dk": lambda x: f"{x:.0f} dk",
            "puan": lambda x: f"{x:.1f}".replace(".", ",")}.get(birim, sayi)(deger)


def _degisim(k):
    d = k["degisim"]
    if d is None or pd.isna(d):
        return "—", None
    iyi = k.get("iyilesme")
    return f"{d * 100:+.1f}%".replace(".", ","), (None if iyi is None or pd.isna(iyi) or iyi == 0 else iyi > 0)


def icerik(veri):
    """Raporun tüm sayıları (PDF'ten bağımsız; test edilebilir)."""
    from analiz import durum
    from tavsiye import motor, urun_karti
    bit = m.veri_araligi(veri)[1]
    bas = bit - pd.Timedelta(days=6)
    ozet = m.ozet(veri, bas, bit, metrikler=[a for a, _ in HAFTALIK]).set_index("ad")
    haftalik = [{"baslik": b, **ozet.loc[a].to_dict()} for a, b in HAFTALIK if a in ozet.index]
    r = durum.durum_raporu(veri)
    liste, _, _ = motor.tavsiyeler(veri)
    plan = motor.aksiyon_plani(liste)
    kartlar, _ = urun_karti.kartlar(veri, liste)
    stok = sorted([k for k in kartlar.values() if "stok_kritik" in k["etiketler"] or "stok_az" in k["etiketler"]],
                  key=lambda k: k["stok"].get("stok_hafta") or 0)
    sikayet = sorted([k for k in kartlar.values() if "sikayetli" in k["etiketler"]],
                     key=lambda k: -(k["musteri_sesi"].get("sikayetli_yorum_payi") or 0))
    h = m.hesapla("ciro_net", veri, kirilim="hafta")
    h.index = pd.to_datetime(h.index)
    h = h[h.index + pd.Timedelta(days=6) <= bit].tail(12)
    dogrulama = json.loads((PROJE / "docs" / "rapor" / "02_dogrulama.json").read_text(encoding="utf-8"))["satirlar"]
    return {
        "veri": veri, "bas": bas, "bit": bit, "haftalik": haftalik,
        "iade_90": m.hesapla("iade_orani", veri, bit - pd.Timedelta(days=89), bit),
        "puan_30": m.hesapla("ortalama_puan", veri, bit - pd.Timedelta(days=29), bit),
        "saglik": r["saglik_skoru"]["skor"],
        "uyarilar": [i for i in r["icgoruler"] if i["yon"] == "olumsuz"][:5],
        "plan": plan, "stok": stok[:5], "sikayet": sikayet[:3], "haftalik_satis": h,
        "dogrulanan": [s["ad"] for s in dogrulama if s["karar"] == "basarili"],
    }


# ====================================================
# 2) PDF
# ====================================================

def _temiz(metin):
    """DejaVu'da olmayan karakterler (emoji) atılır."""
    return re.sub(r"[^\u0000-￿]|[☀-➿️]", "", str(metin)).strip()


class Rapor(FPDF):
    def __init__(self, alt_bilgi):
        super().__init__(format="A4")
        self.alt_bilgi = alt_bilgi
        self.add_font("DejaVu", "", YAZI_TIPI / "DejaVuSans.ttf")
        self.add_font("DejaVu", "B", YAZI_TIPI / "DejaVuSans-Bold.ttf")
        self.set_margins(15, 15, 15)
        self.set_auto_page_break(True, 18)

    def footer(self):
        self.set_y(-12)
        self.set_font("DejaVu", "", 7.5)
        self.set_text_color(*GRI)
        self.cell(0, 5, f"{self.alt_bilgi} · sayfa {self.page_no()}", align="C")

    def baslik(self, metin):
        self.ln(3)
        self.set_font("DejaVu", "B", 12.5)
        self.set_text_color(*VURGU)
        self.cell(0, 8, metin, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*KOYU)

    def paragraf(self, metin, boyut=9.5, renk=KOYU):
        self.set_font("DejaVu", "", boyut)
        self.set_text_color(*renk)
        self.multi_cell(0, 5, _temiz(metin), new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*KOYU)


def _grafik(seri):
    fig, ax = plt.subplots(figsize=(7.2, 2.3), dpi=200)
    ax.bar(seri.index, seri.values / 1000, width=5, color="#2a78d6")
    ax.set_ylabel("bin TL", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.set_xticks(seri.index)
    ax.set_xticklabels([d.strftime("%d.%m") for d in seri.index], rotation=0)
    for k in ("top", "right"):
        ax.spines[k].set_visible(False)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    tampon = io.BytesIO()
    fig.savefig(tampon, format="png")
    plt.close(fig)
    tampon.seek(0)
    return tampon


def pdf_uret(veri, c=None):
    c = c or icerik(veri)
    tarih = f"{c['bas']:%d.%m.%Y} – {c['bit']:%d.%m.%Y}"
    pdf = Rapor(f"{VERI_ADI.get(veri, veri)} · {tarih} · Sistem yalnızca okur ve önerir; Trendyol'a bir şey yazmaz")
    pdf.add_page()
    pdf.set_font("DejaVu", "B", 18)
    pdf.cell(0, 10, "Haftalık Mağaza Raporu", new_x="LMARGIN", new_y="NEXT")
    pdf.paragraf(f"{VERI_ADI.get(veri, veri)} · {tarih} · hazırlanma {datetime.now():%d.%m.%Y %H:%M}", 9, GRI)

    # --- 1) Bu hafta
    pdf.baslik("1. Bu hafta (son 7 gün, önceki 7 günle)")
    with pdf.table(col_widths=(52, 40, 40, 28), text_align=("LEFT", "RIGHT", "RIGHT", "RIGHT"),
                   line_height=6.2, first_row_as_headings=True) as t:
        pdf.set_font("DejaVu", "", 9)
        t.row(["Gösterge", "Bu hafta", "Önceki hafta", "Değişim"])
        for k in c["haftalik"]:
            metin, iyi = _degisim(k)
            satir = t.row([k["baslik"], _bicim(k["deger"], k["birim"]), _bicim(k["onceki"], k["birim"])])
            pdf.set_text_color(*((12, 140, 60) if iyi else (200, 50, 50) if iyi is False else KOYU))
            satir.cell(metin)
            pdf.set_text_color(*KOYU)
    pdf.ln(2)
    pdf.paragraf(f"Sağlık skoru (son 30 gün): {c['saglik']:.0f}/100 · İade oranı (son 90 gün, teslimden 21 gün "
                 f"geçmiş satırlar): {_bicim(c['iade_90'], 'oran')} · Ortalama ürün puanı (son 30 gün): "
                 f"{_bicim(c['puan_30'], 'puan')}", 8.5, GRI)
    if len(c["haftalik_satis"]):
        pdf.ln(1)
        pdf.set_font("DejaVu", "B", 9.5)
        pdf.cell(0, 6, "Haftalık net satış (son 12 tam hafta)", new_x="LMARGIN", new_y="NEXT")
        pdf.image(_grafik(c["haftalik_satis"]), w=180)

    # --- 2) Aksiyon planı
    pdf.baslik("2. Bu haftanın aksiyon planı")
    pdf.paragraf(f"İlk {len(c['plan']['aksiyonlar'])} aksiyon. Ölçülebilenlerin toplam aylık etkisi en fazla "
                 f"{tl(c['plan']['toplam_aylik_etki_tl'])} katkı payı (ürün maliyeti hariç; etkiler kısmen örtüşür).",
                 9, GRI)
    with pdf.table(col_widths=(7, 58, 75, 24, 16), text_align=("RIGHT", "LEFT", "LEFT", "RIGHT", "LEFT"),
                   line_height=4.8, first_row_as_headings=True) as t:
        pdf.set_font("DejaVu", "", 8)
        t.row(["#", "Tavsiye", "Ne yapılmalı", "Aylık etki", "Güven"])
        for x in c["plan"]["aksiyonlar"]:
            t.row([str(x["sira"]), _temiz(x["baslik"]), _temiz(x["aksiyon"]),
                   tl(x["etki_tl"]) if x["etki_tl"] is not None else "ölçülmedi", GUVEN.get(x["guven"], x["guven"])])

    # --- 3) Dikkat
    pdf.baslik("3. Dikkat edilecekler")
    for i in c["uyarilar"]:
        pdf.set_font("DejaVu", "B", 9)
        pdf.multi_cell(0, 5, ("● " if i["onem"] == "yuksek" else "○ ") + _temiz(i["baslik"]), new_x="LMARGIN",
                       new_y="NEXT")
        pdf.paragraf(i["aciklama"], 8.5, GRI)
    if c["stok"]:
        pdf.set_font("DejaVu", "B", 9.5)
        pdf.cell(0, 7, "Stoğu azalan ürünler", new_x="LMARGIN", new_y="NEXT")
        for k in c["stok"]:
            s = k["stok"]
            pdf.paragraf(f"{k['ad']}: {sayi(s['stok'])} adet, haftada {sayi(s['haftalik_hiz'], 1)} satış → "
                         f"{sayi(s['stok_hafta'], 1)} hafta (≈ {pd.Timestamp(s['tukenme_tarihi']):%d.%m.%Y})", 8.5)
    if c["sikayet"]:
        pdf.set_font("DejaVu", "B", 9.5)
        pdf.cell(0, 7, "Şikâyeti en çok olan ürünler", new_x="LMARGIN", new_y="NEXT")
        for k in c["sikayet"]:
            ms = k["musteri_sesi"]
            konu = KONU_ADI.get(ms.get("en_sik_sikayet"), ms.get("en_sik_sikayet") or "")
            pdf.paragraf(f"{k['ad']}: {ms['yorum']} yorum, şikâyetli {yuzde(ms['sikayetli_yorum_payi'], 0)}"
                         + (f", en sık: {konu}" if konu else ""), 8.5)

    # --- 4) Nasıl okunur
    pdf.baslik("4. Bu rapordaki sayılar nasıl okunur")
    pdf.paragraf(
        "Göstergeler mağazanın kendi verisinden hesaplanır. Tavsiyelerin aylık etkisi, gerçekleşen birim değerlerle ve "
        "açıkça yazılmış varsayımlarla hesaplanmış bir üst sınırdır. Fiyat esnekliği ölçülemedi; indirim ve kampanya "
        "tavsiyeleri 1,5 varsayımıyla ve düşük güvenle verilir. Tahmin modelleri sahte veriyle eğitilip gerçek veride "
        f"test edildi; gerçekte doğrulananlar: {', '.join(c['dogrulanan']) or '—'}. Diğer konularda (iade riski, "
        "stok hızı) mağazanın kendi geçmişi kullanılır. Ayrıntı: panel → Model Doğrulama.", 8.5, GRI)
    return bytes(pdf.output())


def kaydet(veri):
    yol = CIKTILAR / veri / f"haftalik_rapor_{m.veri_araligi(veri)[1]:%Y-%m-%d}.pdf"
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_bytes(pdf_uret(veri))
    return yol


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--veri", default="sahte", choices=["sahte", "gercek"])
    print(kaydet(p.parse_args().veri))
