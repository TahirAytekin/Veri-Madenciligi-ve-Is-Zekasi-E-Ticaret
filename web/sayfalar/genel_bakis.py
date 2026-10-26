"""Genel Bakış (F5-02): sağlık skoru, ana göstergeler, en önemli uyarılar, bu haftanın aksiyonları."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from web import ortak
from web.ortak import tl, yuzde

veri = st.session_state.veri
rapor, (tavsiyeler, _, plan), _ = ortak.yukle(veri)
bas, bit = ortak.veri_araligi(veri)

st.title("Genel Bakış")
st.caption(f"Son 30 gün: {ortak.donem_metni(rapor['donem'])} · önceki 30 günle karşılaştırma · veri "
           f"{bas.strftime('%d.%m.%Y')} – {bit.strftime('%d.%m.%Y')}")
ortak.eksik_uyarisi(veri)

# --- Ana göstergeler
BICIM = {"TL": tl, "oran": lambda x: yuzde(x), "puan": lambda x: f"{x:.2f}".replace(".", ","),
         "dk": lambda x: f"{x:.0f} dk", "adet": lambda x: ortak.sayi(x)}
kpi = [k for k in rapor["kpi"] if k["deger"] is not None]
for satir in range(0, len(kpi), 4):
    kolonlar = st.columns(4)
    for kol, k in zip(kolonlar, kpi[satir:satir + 4]):
        bicim = BICIM.get(k["birim"], ortak.sayi)
        degisim = k["degisim"]
        delta = None if degisim is None or pd.isna(degisim) else f"{degisim * 100:+.1f}%".replace(".", ",")
        iyi = k.get("iyilesme")
        kol.metric(k["baslik"], bicim(k["deger"]), delta,
                   delta_color="off" if iyi in (None, 0) or pd.isna(iyi) else ("normal" if iyi > 0 else "inverse"),
                   help=f"Önceki 30 gün: {bicim(k['onceki'])}" if k["onceki"] is not None else None)

st.divider()
sol, sag = st.columns([1, 2])

# --- Sağlık skoru
with sol:
    skor = rapor["saglik_skoru"]
    st.subheader("Sağlık skoru")
    st.markdown(f"<div style='font-size:3.2rem;font-weight:700;line-height:1'>{skor['skor']:.0f}"
                "<span style='font-size:1.2rem;font-weight:400'> / 100</span></div>", unsafe_allow_html=True)
    b = pd.DataFrame([x for x in skor["bilesenler"] if x["puan"] is not None])
    st.plotly_chart(ortak.cubuk(b.baslik, b.puan.round(0), yatay=True, metin=b.puan.round(0),
                                hover="%{y}: %{x:.0f}/100<extra></extra>", yukseklik=260)
                    .update_xaxes(range=[0, 110], visible=False), width="stretch")
    st.caption("Bileşenlerin ortalaması; her bileşen kötü–iyi eşikleri arasında 0–100'e ölçeklenir.")

# --- Haftalık net satış
with sag:
    st.subheader("Haftalık net satış")
    h = ortak.metrik("ciro_net", veri, kirilim="hafta")
    h.index = pd.to_datetime(h.index)
    h = h[h.index + pd.Timedelta(days=6) <= bit].tail(26)          # yarım kalan son hafta yanıltmasın
    fig = go.Figure(go.Scatter(x=h.index, y=h.values, mode="lines+markers", line=dict(width=2, color=ortak.SERI[0]),
                               marker=dict(size=8),
                               hovertemplate="%{x|%d.%m.%Y} haftası<br>%{y:,.0f} TL<extra></extra>"))
    fig.update_yaxes(tickformat=",.0f", ticksuffix=" TL")
    st.plotly_chart(ortak.tema(fig, 330), width="stretch")
    st.caption("Son 26 tam hafta, sipariş tarihine göre (iptaller hariç, iadeler dahil).")

st.divider()
sol, sag = st.columns(2)

# --- En önemli uyarılar
with sol:
    st.subheader("En önemli 5 uyarı")
    sira = {"yuksek": 0, "orta": 1, "dusuk": 2}
    uyarilar = sorted([i for i in rapor["icgoruler"] if i["yon"] == "olumsuz"], key=lambda i: sira[i["onem"]])[:5]
    for i in uyarilar:
        with st.expander(("🔴 " if i["onem"] == "yuksek" else "🟡 ") + i["baslik"]):
            st.write(i["aciklama"])
    if not uyarilar:
        st.success("Olumsuz bir içgörü yok.")

# --- Bu haftanın aksiyonları
with sag:
    st.subheader("Bu haftanın aksiyonları")
    for x in plan["aksiyonlar"][:5]:
        etki = f" · **{tl(x['etki_tl'])}/ay**" if x["etki_tl"] is not None else ""
        st.markdown(f"**{x['sira']}.** {x['baslik']}{etki}  \n↳ {x['aksiyon']}")
    st.page_link("sayfalar/aksiyon_plani.py", label="Tüm plan ve tavsiyeler", icon="✅")

ortak.karar_kutusu("Bu hafta", [
    f"Planın ilk {min(len(plan['aksiyonlar']), 7)} ölçülebilir aksiyonu ayda en fazla "
    f"**{tl(plan['toplam_aylik_etki_tl'])}** katkı payı getirebilir (etkiler kısmen örtüşür).",
    f"İlk iş: **{plan['aksiyonlar'][0]['baslik']}** → {plan['aksiyonlar'][0]['aksiyon']}"
    if plan["aksiyonlar"] else "Plan boş.",
    "Bir uyarının nedenini sormak için Asistan sayfasını kullanın (F5-09).",
])
