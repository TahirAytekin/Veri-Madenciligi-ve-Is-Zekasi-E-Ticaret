"""Talep ve Stok (F5-06): stok tükenme tablosu, ürün başına haftalık satış ve sipariş miktarı hesabı.

Satış hızı = geçen haftanın satışı (o hafta satış yoksa son 4 haftanın ortalaması): gerçek testte en iyi çıkan yöntem.
F2-05 modeli bu referansı geçemediği için yalnızca karşılaştırma olarak gösterilir.
"""
import math

import plotly.graph_objects as go
import streamlit as st

from web import ortak
from web.ortak import sayi

veri = st.session_state.veri
adlar = ortak.urun_adlari(veri)


@st.cache_data(show_spinner="Haftalık satışlar hazırlanıyor…")
def haftalik(veri):
    from modeller.talep import haftalik_seri
    return haftalik_seri(veri)


st.title("Talep ve Stok")
st.caption("Satış = teslim edilen adet (cari hesap 'Satış' kayıtları), tam haftalar. Satış hızı geçen haftanın "
           "satışıdır (gerçek testte haftalık talep modelinden daha isabetli; bkz. Model Doğrulama, F2-05).")
ortak.eksik_uyarisi(veri)

stok = ortak.tahmin(veri, "F2-05_stok")
if stok is None:
    st.info("Stok tablosu yok: `python calistir.py --sadece stok`")
    st.stop()
stok = stok.assign(ürün=stok.model_kodu.map(adlar), temsili_stok=stok.temsili_stok.astype(bool))
gercek = stok[~stok.temsili_stok]

sol, orta, sag = st.columns(3)
tedarik = sol.number_input("Tedarik süresi (hafta)", 1, 12, 3)
hedef = orta.number_input("Siparişten sonra stok kaç hafta yetsin", 1, 26, 6)
k = sag.container()
risk = gercek[(gercek.haftalik_hiz >= 1) & (gercek.stok_hafta < tedarik)]
k.metric("Tedarik süresinden önce tükenecek ürün", len(risk))

st.subheader("Stok tükenme tablosu")
t = gercek.assign(siparis=[math.ceil(max(h * (tedarik + hedef) - s, 0)) for h, s in zip(gercek.haftalik_hiz,
                                                                                          gercek.stok)])
t = t.sort_values("stok_hafta")
st.dataframe(t[["ürün", "kategori", "stok", "haftalik_hiz", "stok_hafta", "tukenme_tarihi", "siparis",
                "tahmin_model"]], hide_index=True, width="stretch",
             column_config={"ürün": st.column_config.TextColumn(width="large"),
                            "haftalik_hiz": st.column_config.NumberColumn("haftalık satış hızı", format="%.1f"),
                            "stok_hafta": st.column_config.NumberColumn("stok kaç hafta yeter", format="%.1f"),
                            "tukenme_tarihi": "tahmini tükenme",
                            "siparis": st.column_config.NumberColumn("önerilen sipariş", format="%d",
                                                                     help="hız × (tedarik + hedef) − stok"),
                            "tahmin_model": st.column_config.NumberColumn(
                                "model tahmini (gelecek hafta)", format="%.1f",
                                help="F2-05; gerçek testte referansı geçemedi, yalnızca karşılaştırma için")})
st.caption(f"{len(stok) - len(gercek)} üründe stok temsili (varyant stoğu ≥ 900, satıcının yazdığı sembolik sayı); "
           "bunlarda süre hesaplanmaz ve tabloda yoktur.")

# --- Ürün ayrıntısı
st.subheader("Ürünün haftalık satışı")
seri = haftalik(veri)
kodlar = list(t.model_kodu) + sorted(set(stok.model_kodu) - set(t.model_kodu))
kod = ortak.urun_secimi("Ürün", kodlar, adlar)
s = seri[seri.model_kodu == kod].tail(26)
r = stok[stok.model_kodu == kod].iloc[0]
fig = go.Figure(go.Bar(x=s.hafta, y=s.adet, name="satış", marker=dict(color=ortak.SERI[0], cornerradius=4),
                       hovertemplate="%{x|%d.%m.%Y} haftası: %{y} adet<extra></extra>"))
fig.add_trace(go.Scatter(x=[r.hafta], y=[r.haftalik_hiz], mode="markers", name="satış hızı (gelecek hafta)",
                         marker=dict(size=12, symbol="diamond", color=ortak.SERI[1])))
st.plotly_chart(ortak.tema(fig, 300), width="stretch")
if r.temsili_stok:
    st.markdown(f"Stok temsili ({sayi(r.stok)}); süre hesaplanmaz. Satış hızı haftada {sayi(r.haftalik_hiz, 1)}.")
else:
    st.markdown(f"Stok **{sayi(r.stok)}** adet, haftada **{sayi(r.haftalik_hiz, 1)}** satış → yaklaşık "
                f"**{sayi(r.stok_hafta, 1)} hafta** yeter (≈ {r.tukenme_tarihi}).")

ortak.karar_kutusu("Karar", [
    f"{len(risk)} ürünün stoğu tedarik süresinden ({tedarik} hafta) önce bitiyor: tablodaki 'önerilen sipariş' "
    "kadar sipariş verin." if len(risk) else f"Hiçbir ürünün stoğu {tedarik} haftadan önce bitmiyor.",
    "Sezon geçişlerinde (yaz/kış) satış hızı hızla değişir; Aksiyon Planı'ndaki sezon hazırlığı tavsiyelerine bakın.",
])
