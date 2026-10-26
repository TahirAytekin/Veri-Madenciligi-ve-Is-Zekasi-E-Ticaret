"""Ürünler (F5-04): portföy matrisi, filtreli ürün listesi, ürün sağlık kartı ve ürüne özel tavsiyeler."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from web import ortak
from web.ortak import sayi, tl, yuzde

veri = st.session_state.veri
_, _, (kartlar, bilgi) = ortak.yukle(veri)

st.title("Ürünler")
st.caption(f"Son 90 gün: {ortak.donem_metni(bilgi['donem'])} · mağaza iade oranı {yuzde(bilgi['magaza_iade_orani'])}. "
           "Etiket kuralları: docs/TAVSIYE_KURALLARI.md → Ürün sağlık kartı")
ortak.eksik_uyarisi(veri)

t = pd.DataFrame([{
    "model_kodu": k["model_kodu"], "ürün": k["ad"], "kategori": k["kategori"], "durum": k["durum"],
    "etiketler": ortak.etiketler_metni(k["etiketler"]), "adet_90": k["satis"]["adet_90"],
    "ciro_90": k["satis"]["ciro_90"], "ciro_degisimi": k["satis"]["ciro_degisimi"],
    "katki_marji": k["karlilik"].get("katki_marji"), "iade": k["iade"].get("oran"),
    "puan": k["musteri_sesi"].get("ortalama_puan"), "tavsiye": len(k["tavsiyeler"]),
} for k in kartlar.values()])

d = t.durum.value_counts()
k1, k2, k3, k4 = st.columns(4)
k1.metric("Ürün", len(t))
k2.metric(ortak.DURUM_ETIKET["iyi"], int(d.get("iyi", 0)))
k3.metric(ortak.DURUM_ETIKET["dikkat"], int(d.get("dikkat", 0)))
k4.metric(ortak.DURUM_ETIKET["sorunlu"], int(d.get("sorunlu", 0)))

# --- Portföy matrisi
st.subheader("Portföy: satış × kârlılık")
p = t[(t.ciro_90 > 0) & t.katki_marji.notna()]
fig = go.Figure()
for durum in ("iyi", "dikkat", "sorunlu"):
    x = p[p.durum == durum]
    fig.add_trace(go.Scatter(
        x=x.ciro_90, y=x.katki_marji * 100, mode="markers", name=ortak.DURUM_ETIKET[durum],
        marker=dict(size=(x.adet_90.clip(lower=1) ** 0.5) * 3 + 6, color=ortak.DURUM_RENK[durum], opacity=0.75,
                    line=dict(width=1, color="white")),
        customdata=x[["ürün", "adet_90", "etiketler"]],
        hovertemplate="<b>%{customdata[0]}</b><br>net satış %{x:,.0f} TL · katkı marjı %{y:.0f}%<br>"
                      "%{customdata[1]} adet · %{customdata[2]}<extra></extra>"))
if len(p):
    fig.add_hline(y=p.katki_marji.median() * 100, line=dict(dash="dot", width=1, color="gray"))
    fig.add_vline(x=p.ciro_90.median(), line=dict(dash="dot", width=1, color="gray"))
fig.update_xaxes(type="log", title="net satış, son 90 gün (TL, log)")
fig.update_yaxes(title="katkı marjı (%)", ticksuffix="%")
st.plotly_chart(ortak.tema(fig, 420), width="stretch")
st.caption("Kesikli çizgiler medyanlar. Sağ üst: çok satan ve kârlı (koru, stok ayır) · sağ alt: çok satan ama marjı "
           "düşük (fiyat/indirim/iade) · sol üst: kârlı ama az satan (görünürlük, kampanya) · sol alt: gözden geçir. "
           "Nokta büyüklüğü satılan adet.")

# --- Liste
st.subheader("Ürün listesi")
sol, orta, sag = st.columns(3)
durumlar = sol.multiselect("Durum", ["sorunlu", "dikkat", "iyi"], format_func=ortak.DURUM_ETIKET.get)
kategoriler = orta.multiselect("Kategori", sorted(t.kategori.dropna().unique()))
etiket = sag.selectbox("Etiket", ["(hepsi)"] + list(ortak.ETIKET_ADI), format_func=lambda e: ortak.ETIKET_ADI.get(e, e))
s = t[ortak.filtre(t.durum, durumlar) & ortak.filtre(t.kategori, kategoriler)]
if etiket != "(hepsi)":
    s = s[s.model_kodu.map(lambda k: etiket in kartlar[k]["etiketler"])]
s = s.assign(_sira=s.durum.map({"sorunlu": 0, "dikkat": 1, "iyi": 2})).sort_values(["_sira", "ciro_90"],
                                                                                 ascending=[True, False])
st.dataframe(
    s.assign(durum=s.durum.map(ortak.DURUM_ETIKET), katki_marji=s.katki_marji * 100, iade=s.iade * 100,
             ciro_degisimi=s.ciro_degisimi * 100).drop(columns=["_sira"]),
    hide_index=True, width="stretch",
    column_config={"model_kodu": None, "ürün": st.column_config.TextColumn(width="large"),
                   "adet_90": st.column_config.NumberColumn("adet (90 g)", format="%d"),
                   "ciro_90": st.column_config.NumberColumn("net satış (90 g)", format="%,.0f TL"),
                   "ciro_degisimi": st.column_config.NumberColumn("satış değişimi", format="%+.0f%%",
                                                                  help="son 30 gün / önceki 30 gün"),
                   "katki_marji": st.column_config.NumberColumn("katkı marjı", format="%.0f%%"),
                   "iade": st.column_config.NumberColumn("iade oranı", format="%.1f%%",
                                                         help="boş: 30'dan az olgun teslim"),
                   "puan": st.column_config.NumberColumn(format="%.1f"), "tavsiye": "tavsiye sayısı"})

# --- Ürün sağlık kartı
st.divider()
st.subheader("Ürün sağlık kartı")
secenekler = {f"{kartlar[k]['ad']} ({k})": k for k in (s.model_kodu.tolist() or t.model_kodu.tolist())}
kod = secenekler[st.selectbox("Ürün", list(secenekler))]
k = kartlar[kod]
st.markdown(f"### {k['ad']}\n{ortak.durum_rozeti(k['durum'])} · {k['kategori'] or '—'} · etiketler: "
            f"{ortak.etiketler_metni(k['etiketler'])}")

sat, kar, iad = k["satis"], k["karlilik"], k["iade"]
c = st.columns(5)
degisim = sat["ciro_degisimi"]
c[0].metric("Net satış (90 g)", tl(sat["ciro_90"]),
            None if degisim is None else f"{degisim * 100:+.0f}% (30 g)".replace(".", ","))
c[1].metric("Adet (90 g)", sayi(sat["adet_90"]))
c[2].metric("Katkı payı (90 g)", tl(kar["katki_payi_90"]) if kar else "—",
            help="ürün maliyeti hariç; iade, kargo, komisyon ve platform payı düşülmüş")
c[3].metric("Katkı marjı", yuzde(kar["katki_marji"], 0) if kar and kar.get("katki_marji") is not None else "—")
c[4].metric("İade oranı", yuzde(iad["oran"]) if iad and iad.get("oran") is not None else "—",
            None if not iad or iad.get("oran") is None else
            f"{(iad['oran'] - iad['magaza_orani']) * 100:+.1f} puan mağazaya göre".replace(".", ","),
            delta_color="inverse")

sol, sag = st.columns([3, 2])
with sol:
    hafta = pd.to_datetime(bilgi["haftalar"][-len(sat["haftalik_adet"]):]) if sat["haftalik_adet"] else []
    st.plotly_chart(ortak.cubuk(hafta, sat["haftalik_adet"], "Haftalık satış (adet, son 12 hafta)",
                                hover="%{x|%d.%m} haftası: %{y} adet<extra></extra>", yukseklik=260),
                    width="stretch")
with sag:
    ka, ms, st_ = k["kalip"], k["musteri_sesi"], k["stok"]
    satirlar = []
    if ka:
        satirlar.append(f"**Kalıp:** {ka['etiket']} — {sayi(ka['beden_iadesi'])} beden iadesinin "
                        f"{yuzde(ka['skor'], 0)} kadarı 'küçük geldi'")
    if ms:
        konu = f"; en sık şikâyet: {ms['en_sik_sikayet'].replace('_', '/')}" if ms["en_sik_sikayet"] else ""
        satirlar.append(f"**Müşteri sesi:** {ms['yorum']} yorum, puan {ms['ortalama_puan']:.1f}".replace(".", ",")
                        + f", şikâyetli yorum {yuzde(ms['sikayetli_yorum_payi'], 0)}{konu}")
    if st_:
        if st_["temsili"]:
            satirlar.append(f"**Stok:** temsili ({sayi(st_['stok'])}); süre hesaplanmaz")
        else:
            satirlar.append(f"**Stok:** {sayi(st_['stok'])} adet, haftada {sayi(st_['haftalik_hiz'], 1)} satış → "
                            f"{sayi(st_['stok_hafta'], 1)} hafta (≈ {st_['tukenme_tarihi']})")
    if kar:
        satirlar.append(f"**Birim:** net fiyat {tl(kar['birim_net_fiyat'])}, birim katkı {tl(kar['birim_katki'])}, "
                        f"indirim {yuzde(kar['indirim_orani'], 0)}")
    st.markdown("  \n".join(satirlar) or "Ek bilgi yok.")

if k["tavsiyeler"]:
    ortak.karar_kutusu("Bu ürün için", [
        f"{x['baslik']} → {x['aksiyon']}" + (f" (**{tl(x['etki_tl'])}/ay**)" if x["etki_tl"] is not None else "")
        for x in k["tavsiyeler"]])
else:
    ortak.karar_kutusu("Bu ürün için", ["Bu ürüne özel bir tavsiye yok."])
