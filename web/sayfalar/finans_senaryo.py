"""Finans ve Senaryo (F5-07): katkı payı şelalesi ve "ne olur" simülatörü (analiz/senaryo.py)."""
import plotly.graph_objects as go
import streamlit as st

from web import ortak
from web.ortak import tl, yuzde

veri = st.session_state.veri
KALEMLER = [("net_satis", "Net satış"), ("iade_tutari", "İadeler"), ("komisyon", "Komisyon"), ("kargo", "Kargo"),
            ("platform", "Platform hizmet"), ("iade_kargo", "İade kargosu")]


def selale(t, baslik):
    """Net satıştan katkı payına: her kalem bir düşüş."""
    olcu = ["absolute"] + ["relative"] * (len(KALEMLER) - 1) + ["total"]
    degerler = [t["net_satis"]] + [-t[k] for k, _ in KALEMLER[1:]] + [t["katki_payi"]]
    adlar = [a for _, a in KALEMLER] + ["Katkı payı"]
    fig = go.Figure(go.Waterfall(
        x=adlar, y=degerler, measure=olcu, text=[tl(abs(v)) for v in degerler], textposition="outside",
        connector=dict(line=dict(color="rgba(128,128,128,0.4)")), decreasing=dict(marker=dict(color="#e34948")),
        increasing=dict(marker=dict(color=ortak.SERI[0])), totals=dict(marker=dict(color="#1baf7a")),
        hovertemplate="%{x}: %{y:,.0f} TL<extra></extra>"))
    fig.update_layout(title=dict(text=baslik, font=dict(size=14)), showlegend=False)
    fig.update_yaxes(tickformat=",.0f", ticksuffix=" TL")
    return ortak.tema(fig, 380)


st.title("Finans ve Senaryo")
st.caption("Katkı payı = net satış − iadeler − komisyon − kargo − platform − iade kargosu (ürün maliyeti hariç). "
           "Son 90 günün gerçekleşen değerleriyle; senaryo yalnızca seçilen kalemi değiştirir.")

baz = ortak.senaryo(veri)
b = baz["baz"]
k = st.columns(4)
k[0].metric("Net satış (90 g)", tl(b["net_satis"]))
k[1].metric("Katkı payı (90 g)", tl(b["katki_payi"]))
k[2].metric("Katkı marjı", yuzde(b["katki_payi"] / b["net_satis"], 0) if b["net_satis"] else "—")
k[3].metric("İade oranı", yuzde(baz["baz_degerler"]["iade_orani"]))
st.plotly_chart(selale(b, f"Son 90 gün ({ortak.donem_metni(baz['donem'])})"), width="stretch")

# --- Senaryo
st.divider()
st.subheader("Ne olur?")
sol, sag = st.columns(2)
with sol:
    beden = st.slider("Beden kaynaklı iadeler azalırsa (%)", 0, 100, 0, 5)
    iade = st.slider("Tüm iadeler azalırsa (%)", 0, 100, 0, 5)
    indirim = st.slider("Ek indirim (%)", 0, 50, 0, 1)
    esneklik = st.slider("Fiyat esnekliği (indirimde satış artışı)", 0.0, 4.0, 0.0, 0.25,
                         help="0: satış adedi değişmez. 1,5: %10 indirimde satış ≈ %17 artar. Bu mağaza için "
                              "ölçülmedi.",
                         disabled=indirim == 0)
with sag:
    komisyon = st.slider("Komisyon değişimi (puan)", -10.0, 10.0, 0.0, 0.5)
    desi = st.slider("Paket başına desi azalışı", 0, 5, 0)
    maliyet_var = st.toggle("Ürün maliyetini de hesaba kat (net kâr)")
    maliyet = st.slider("Ürün maliyeti / net satış fiyatı (%)", 10, 90, 40, 5, disabled=not maliyet_var)

s = ortak.senaryo(veri, beden_iade_azalis=beden / 100, iade_azalis=iade / 100, ek_indirim=indirim / 100,
                  esneklik=esneklik if indirim and esneklik else None, komisyon_farki=komisyon, desi_azalis=desi,
                  maliyet_orani=maliyet / 100 if maliyet_var else None)
f = s["fark"]
k = st.columns(3)
aylik_baz = b["katki_payi"] / baz["donem"]["gun"] * 30
k[0].metric("Aylık katkı payı farkı", tl(s["aylik_katki_farki"]),
            f"{s['aylik_katki_farki'] / aylik_baz * 100:+.1f}%".replace(".", ",") if aylik_baz else None)
k[1].metric("Senaryoda iade oranı", yuzde(s["senaryo_iade_orani"]))
if maliyet_var:
    k[2].metric("Net kâr (90 g)", tl(s["senaryo"]["net_kar"]), tl(f["net_kar"]))
st.success(s["ozet"])
if "basa_bas" in s:
    st.info(f"**Başa baş:** {s['basa_bas']['aciklama']}")
c1, c2 = st.columns(2)
c1.plotly_chart(selale(b, "Bugün (90 g)"), width="stretch")
c2.plotly_chart(selale(s["senaryo"], "Senaryo (90 g)"), width="stretch")
with st.expander("Varsayımlar"):
    for v in s["varsayimlar"]:
        st.markdown(f"- {v}")

ortak.karar_kutusu("Nasıl okunur", [
    "Önce beden iadelerini azaltan aksiyonlar: kaydırıcı %30'dayken aylık etkiyi Aksiyon Planı'ndaki "
    "'beden önerici' tavsiyesiyle karşılaştırın.",
    "İndirim kararından önce başa baş satış artışına bakın; gerekli artış gerçekçi değilse indirim katkıyı düşürür.",
    "Desi kazancı Trendyol Express'te 3 desi ve üstünde başlar (0–2 desi aynı ücret).",
])
