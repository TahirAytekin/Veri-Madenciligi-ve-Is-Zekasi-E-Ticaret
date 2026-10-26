"""İade ve Beden (F5-05): iade nedenleri, kategori iade oranları, kalıp tablosu ve beden öneri aracı."""
import pandas as pd
import streamlit as st

from analiz import metrikler as m
from web import ortak
from web.ortak import sayi, yuzde

veri = st.session_state.veri
bas, bit = ortak.veri_araligi(veri)
d90 = bit - pd.Timedelta(days=89)
adlar = ortak.urun_adlari(veri)
NEDEN_ADI = {"beden_kucuk": "küçük geldi", "beden_buyuk": "büyük geldi", "begenmedim": "beğenmedim",
             "kusurlu": "kusurlu", "yanlis_eksik_urun": "yanlış/eksik ürün", "vazgecti": "vazgeçti", "diger": "diğer"}

st.title("İade ve Beden")
st.caption(f"Son 90 gün: {d90.strftime('%d.%m.%Y')} – {bit.strftime('%d.%m.%Y')}. İade oranı yalnızca teslimi "
           f"üzerinden {m.OLGUNLASMA_GUN} gün geçmiş satırlardan hesaplanır.")
ortak.eksik_uyarisi(veri)

oran, beden_payi = ortak.metrik("iade_orani", veri, d90, bit), ortak.metrik("beden_kaynakli_iade_payi", veri, d90, bit)
k1, k2, k3 = st.columns(3)
k1.metric("İade oranı", yuzde(oran))
k2.metric("Beden kaynaklı iade payı", yuzde(beden_payi, 0))
k3.metric("İade adedi", sayi(ortak.metrik("iade_adet", veri, d90, bit)))

sol, sag = st.columns(2)
with sol:
    i = m.tablolar(veri)["iadeler"]
    i = i[(i.iade_tarihi >= d90) & (i.durum == "Accepted") & (i.neden_grubu != "teslim_edilemedi")]
    n = i.neden_grubu.map(lambda x: NEDEN_ADI.get(x, x)).value_counts()
    st.plotly_chart(ortak.cubuk(n.index, n.values, "İade nedenleri (kabul edilen)", yatay=True, metin=n.values,
                                hover="%{y}: %{x}<extra></extra>"), width="stretch")
with sag:
    k = ortak.metrik("iade_orani", veri, d90, bit, kirilim="kategori").dropna().sort_values(ascending=False)
    st.plotly_chart(ortak.cubuk(k.index, (k.values * 100).round(1), "Kategoriye göre iade oranı (%)", yatay=True,
                                metin=[yuzde(x) for x in k.values], hover="%{y}: %{x:.1f}%<extra></extra>"),
                    width="stretch")
    st.caption(f"{m.MIN_ORNEK}'dan az olgun teslimi olan kategoriler gösterilmez.")

# --- Kalıp tablosu
st.subheader("Kalıp tablosu")
kalip = ortak.tahmin(veri, "F2-04_kalip")
if kalip is None:
    st.info("Kalıp tablosu yok: `python calistir.py --sadece kalip`")
else:
    kalip = kalip.assign(ürün=kalip.model_kodu.map(adlar))
    goster = st.radio("Göster", ["dar ve bol", "hepsi"], horizontal=True)
    t = kalip[kalip.kalip.isin(["dar", "bol"])] if goster == "dar ve bol" else kalip
    t = t.sort_values(["beden_iadesi"], ascending=False)
    st.dataframe(t[["ürün", "kategori", "kalip", "kalip_skoru", "beden_iadesi", "beden_iade_orani"]]
                 .assign(kalip_skoru=t.kalip_skoru * 100, beden_iade_orani=t.beden_iade_orani * 100),
                 hide_index=True, width="stretch",
                 column_config={"ürün": st.column_config.TextColumn(width="large"),
                                "kalip": "kalıp",
                                "kalip_skoru": st.column_config.ProgressColumn(
                                    "'küçük geldi' payı", format="%.0f%%", min_value=0, max_value=100,
                                    help="beden iadelerinin yüzde kaçı 'küçük geldi'"),
                                "beden_iadesi": st.column_config.NumberColumn("beden iadesi", format="%d"),
                                "beden_iade_orani": st.column_config.NumberColumn("beden iade oranı",
                                                                                  format="%.1f%%")})
    st.caption("Kalıp etiketi en az 5 beden iadesi olan ürünlere verilir. Gerçek veride zayıf ama doğru yönde bir "
               "sinyaldir (F2-04A, AUC 0,59); kanıt sayısıyla birlikte okuyun.")

# --- Beden önerici
st.divider()
st.subheader("Beden önerici")
st.caption("Boy ve kiloya göre harf beden; kalıbı dar/bol üründe bir beden kaydırılır. Gerçek veride iki testte "
           "doğrulandı (F2-04C, F3-04): satıcının önerdiği bedenle %45–50 tam, %94–96 ±1 beden aynı.")
from modeller.beden_uyumu import beden_oner  # noqa: E402

sol, orta, sag = st.columns([1, 1, 2])
boy = sol.number_input("Boy (cm)", 140, 210, 165)
kilo = orta.number_input("Kilo (kg)", 35, 150, 58)
kodlar = sorted(kalip.model_kodu) if kalip is not None else []
with sag:
    kod = ortak.urun_secimi("Ürün (isteğe bağlı, kalıp için)", ["(ürün seçmeden)"] + kodlar, adlar)
satir = kalip[kalip.model_kodu == kod].iloc[0] if kalip is not None and kod in set(kalip.model_kodu) else None
oneri = beden_oner(boy, kilo, satir.kalip_skoru if satir is not None else None,
                   satir.beden_iadesi if satir is not None else None)
genel = beden_oner(boy, kilo)
with st.container(border=True):
    st.markdown(f"### Önerilen beden: **{oneri}**")
    if satir is not None and oneri != genel:
        st.markdown(f"Ürünün kalıbı **{satir.kalip}** ({sayi(satir.beden_iadesi)} beden iadesi); kalıp dikkate "
                    f"alınmasaydı öneri **{genel}** olurdu.")
    elif satir is not None:
        st.markdown(f"Ürünün kalıbı: {satir.kalip}. Öneri kalıptan etkilenmedi.")

ortak.karar_kutusu("Karar", [
    f"İadelerin {yuzde(beden_payi, 0)} kadarı beden kaynaklı: beden önericiyi ürün açıklamalarına ve beden "
    "sorularının cevaplarına ekleyin.",
    "Kalıbı dar/bol çıkan ürünlerin sayfasına 'bir beden büyük/küçük alın' notu yazın.",
    "Beden sorularına hızlı cevap için Müşteri Sesi → Cevap önerici.",
])
