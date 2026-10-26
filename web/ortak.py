"""Web uygulamasının ortak parçaları (F5-01): veri seçimi, önbellekli yükleyiciler, biçim, grafik teması, bileşenler.

Kural: sayfalar sayı hesaplamaz; analiz/, tavsiye/, modeller/ ve ciktilar/ içinden okur. Her sayfa bir karar veya
aksiyonla biter (karar_kutusu).
"""
import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analiz import metrikler as m
from analiz.durum import sayi, tl, yuzde
from hazirlama.ortak import PROJE, VERI
from modeller.ortak.degerlendir import CIKTILAR

__all__ = ["sayi", "tl", "yuzde"]

# Grafik renkleri: doğrulanmış referans palet (dataviz), açık tema adımları. Durum renkleri ayrı ve yalnızca durum için.
SERI = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
DURUM_RENK = {"iyi": "#0ca30c", "dikkat": "#fab219", "sorunlu": "#d03b3b"}
DURUM_ETIKET = {"iyi": "✅ iyi", "dikkat": "⚠️ dikkat", "sorunlu": "⛔ sorunlu"}
GUVEN_ETIKET = {"yuksek": "🟢 yüksek", "orta": "🟡 orta", "dusuk": "🔴 düşük"}
ETIKET_ADI = {"zarar": "zarar ediyor", "yuksek_iade": "yüksek iade", "iade_artisi": "iade artıyor",
              "kalip_dar": "kalıbı dar", "kalip_bol": "kalıbı bol", "sikayetli": "şikâyetli",
              "satis_dusuyor": "satış düşüyor", "satis_artiyor": "satış artıyor", "olu_stok": "ölü stok",
              "stok_kritik": "stok kritik", "stok_az": "stok az"}
GEREKLI_CIKTILAR = {"F2-04_kalip": "python -m modeller.beden_uyumu", "F2-05_stok": "python -m modeller.talep",
                    "F2-06_urun": "python -m modeller.duygu"}


# ====================================================
# 1) VERİ SEÇİMİ
# ====================================================

def veri_setleri():
    return [v for v in ("gercek", "sahte") if (VERI / v / "siparisler.csv").exists()]


def veri_secici():
    """Kenar çubuğunda veri seti seçimi; seçim oturum boyunca saklanır."""
    secenekler = veri_setleri()
    if "veri" not in st.session_state:
        st.session_state.veri = secenekler[0]
    adlar = {"gercek": "Gerçek mağaza", "sahte": "Sahte (demo)"}
    st.sidebar.radio("Veri", secenekler, key="veri", format_func=adlar.get)
    if st.session_state.veri == "gercek":
        st.sidebar.caption("Gerçek mağaza verisi. Bu ekranı paylaşmayın.")
    return st.session_state.veri


def eksik_ciktilar(veri):
    return {ad: komut for ad, komut in GEREKLI_CIKTILAR.items()
            if not (CIKTILAR / veri / "tahminler" / f"{ad}.csv").exists()}


def eksik_uyarisi(veri):
    eksik = eksik_ciktilar(veri)
    if eksik:
        st.warning("Bazı model çıktıları yok; ilgili bölümler boş kalır. Hepsini hazırlamak için: "
                   "`python -m web.hazirla`  \n" + "\n".join(f"- `{k}` → `{v}`" for k, v in eksik.items()))


# ====================================================
# 2) ÖNBELLEKLİ YÜKLEYİCİLER
# ====================================================

def _surum(veri):
    """Önbellek anahtarı: model çıktıları yeniden üretilince veriler de yenilensin. Yükleyicilerde parametre adı alt
    çizgiyle başlamamalı: Streamlit '_' ile başlayan parametreleri önbellek anahtarına katmaz."""
    klasor = CIKTILAR / veri / "tahminler"
    return max((p.stat().st_mtime for p in klasor.glob("*.csv")), default=0) if klasor.exists() else 0


@st.cache_data(show_spinner="Durum raporu hazırlanıyor…")
def durum_raporu(veri, surum=None):
    from analiz import durum
    return durum.durum_raporu(veri)


@st.cache_data(show_spinner="Tavsiyeler hesaplanıyor…")
def tavsiyeler(veri, surum=None):
    from tavsiye import motor
    liste, hatalar, _ = motor.tavsiyeler(veri)
    return [t.sozluk() for t in liste], hatalar, motor.aksiyon_plani(liste)


@st.cache_data(show_spinner="Ürün kartları hazırlanıyor…")
def kartlar(veri, surum=None):
    from tavsiye import motor, urun_karti
    liste, _, _ = motor.tavsiyeler(veri)
    k, bilgi = urun_karti.kartlar(veri, liste)
    return k, bilgi


@st.cache_data
def dogrulama():
    return json.loads((PROJE / "docs" / "rapor" / "02_dogrulama.json").read_text(encoding="utf-8"))


@st.cache_data
def dogrulama_yorumu():
    metin = (PROJE / "docs" / "rapor" / "02_dogrulama.md").read_text(encoding="utf-8")
    return metin.split("<!-- YORUM -->")[1].split("<!-- /YORUM -->")[0] if "<!-- YORUM -->" in metin else ""


@st.cache_data
def metrik(ad, veri, baslangic=None, bitis=None, kirilim=None):
    return m.hesapla(ad, veri, baslangic, bitis, kirilim=kirilim)


@st.cache_data
def veri_araligi(veri):
    return m.veri_araligi(veri)


@st.cache_data
def cikti(veri, ad, surum=None):
    """ciktilar/<veri>/tahminler/<ad>.csv (yoksa None)."""
    yol = CIKTILAR / veri / "tahminler" / f"{ad}.csv"
    return pd.read_csv(yol, encoding="utf-8-sig") if yol.exists() else None


def tahmin(veri, ad):
    return cikti(veri, ad, _surum(veri))


@st.cache_data
def urun_adlari(veri):
    u = m.tablolar(veri)["urunler"].dropna(subset=["model_kodu"])
    return u.groupby("model_kodu").urun_adi.first().to_dict()


@st.cache_data(show_spinner="Senaryo hesaplanıyor…")
def senaryo(veri, **parametreler):
    from analiz.senaryo import simule
    return simule(veri, **parametreler)


def urun_secimi(etiket, kodlar, adlar, key=None):
    """Ürün seçimi: görünen ad → model kodu (format_func kullanılmaz; testte de aynı çalışır)."""
    secenekler = {f"{adlar.get(k, k)} ({k})": k for k in kodlar}
    secim = st.selectbox(etiket, list(secenekler), key=key)
    return secenekler.get(secim)


def yukle(veri):
    """Sayfaların kullandığı üç ana kaynak (önbellekli; çıktılar değişince yenilenir)."""
    s = _surum(veri)
    return durum_raporu(veri, s), tavsiyeler(veri, s), kartlar(veri, s)


# ====================================================
# 3) BİLEŞENLER
# ====================================================

def tema(fig, yukseklik=320):
    """Grafik teması: şeffaf zemin (açık/koyu temaya uyar), sessiz ızgara, tek eksen, palet sırası."""
    fig.update_layout(height=yukseklik, margin=dict(l=8, r=8, t=32, b=8), colorway=SERI,
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(size=13), legend=dict(orientation="h", y=1.08, x=0),
                      hoverlabel=dict(font_size=13), separators=",.")
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.18)", zeroline=False)
    return fig


def cubuk(x, y, baslik="", yatay=False, metin=None, renk=SERI[0], yukseklik=320, hover=None):
    fig = go.Figure(go.Bar(x=y if yatay else x, y=x if yatay else y, orientation="h" if yatay else "v",
                           marker=dict(color=renk, cornerradius=4), text=metin, textposition="outside",
                           hovertemplate=hover))
    fig.update_layout(title=dict(text=baslik, font=dict(size=14)), bargap=0.35)
    if yatay:
        fig.update_yaxes(autorange="reversed")
    return tema(fig, yukseklik)


def filtre(sutun, secilenler):
    """Çoklu seçim filtresi: hiçbir şey seçilmediyse hepsi."""
    return sutun.isin(secilenler) if secilenler else pd.Series(True, index=sutun.index)


def durum_rozeti(durum):
    return DURUM_ETIKET.get(durum, durum)


def etiketler_metni(etiketler):
    return ", ".join(ETIKET_ADI.get(e, e) for e in etiketler) or "—"


def karar_kutusu(baslik, maddeler):
    """Her sayfanın sonundaki karar/aksiyon özeti."""
    with st.container(border=True):
        st.markdown(f"**🎯 {baslik}**")
        for madde in maddeler:
            st.markdown(f"- {madde}")


def tavsiye_satiri(t):
    etki = tl(t["etki_tl"]) + "/ay" if t["etki_tl"] is not None else "ölçülmedi"
    return {"öncelik": t.get("sira"), "tavsiye": t["baslik"], "aksiyon": t["aksiyon"], "aylık etki": etki,
            "güven": GUVEN_ETIKET.get(t["guven"], t["guven"]), "alan": t["alan"]}


def donem_metni(donem):
    bas, bit = (pd.Timestamp(donem[k]).strftime("%d.%m.%Y") for k in ("baslangic", "bitis"))
    return f"{bas} – {bit}"
