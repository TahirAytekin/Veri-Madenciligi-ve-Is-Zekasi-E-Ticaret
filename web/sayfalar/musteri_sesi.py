"""Müşteri Sesi (F5-08): yorum puanları, şikâyet konuları, şikâyetli ürünler ve müşteri sorusu cevap önerici."""
import streamlit as st

from analiz import metrikler as m
from hazirlama.ortak import env_degeri
from web import demo, ortak
from web.ortak import sayi, yuzde

veri = st.session_state.veri
adlar = ortak.urun_adlari(veri)
KONU_ADI = {"beden_kalip": "beden/kalıp", "kumas_kalite": "kumaş/kalite", "kargo_paket": "kargo/paket",
            "renk_gorsel": "renk/görsel", "urun_hatasi": "ürün hatası", "fiyat": "fiyat"}

st.title("Müşteri Sesi")
st.caption("Şikâyet tespiti hazır Türkçe BERT modeliyle (F2-06; gerçek yorumlarda AUC 0,91), konular kurallarla. "
           "BERT yorumun puanından çok metnindeki şikâyeti yakalar: 5 yıldızlı yorumda bile şikâyet olabilir.")
ortak.eksik_uyarisi(veri)

y = ortak.tahmin(veri, "F2-06")
if y is None:
    st.info("Yorum analizi yok: `python calistir.py --sadece yorum`")
else:
    k = st.columns(4)
    k[0].metric("Yorum", sayi(len(y)))
    k[1].metric("Ortalama puan", f"{y.puan.mean():.2f}".replace(".", ","))
    k[2].metric("Şikâyet içeren yorum", yuzde(y.sikayet_iceriyor.mean(), 0))
    k[3].metric("4–5 yıldızlı ama şikâyetli", yuzde(y[y.puan >= 4].sikayet_iceriyor.mean(), 0))

    sol, sag = st.columns(2)
    with sol:
        p = y.groupby("puan").agg(yorum=("puan", "size"), sikayet=("sikayet_iceriyor", "mean"))
        fig = ortak.cubuk([f"{int(i)}★" for i in p.index], p.yorum, "Puan dağılımı", metin=p.yorum,
                          hover="%{x}: %{y} yorum<extra></extra>")
        st.plotly_chart(fig, width="stretch")
        st.caption("Şikâyetli yorum payı: " + " · ".join(f"{int(i)}★ {yuzde(v, 0)}" for i, v in p.sikayet.items()))
    with sag:
        konu = (y[y.sikayet_iceriyor].konular.dropna().str.split(",").explode().map(lambda x: KONU_ADI.get(x, x))
                .value_counts())
        st.plotly_chart(ortak.cubuk(konu.index, konu.values, "Şikâyet konuları", yatay=True, metin=konu.values,
                                    renk=ortak.SERI[1], hover="%{y}: %{x} yorum<extra></extra>"), width="stretch")

    u = ortak.tahmin(veri, "F2-06_urun")
    if u is not None:
        st.subheader("Şikâyetli ürünler")
        u = u[u.yorum >= 3].assign(ürün=u.model_kodu.map(adlar),
                                   en_sik_sikayet=u.en_sik_sikayet.map(lambda x: KONU_ADI.get(x, x)))
        u = u.sort_values(["sikayetli_yorum_payi", "yorum"], ascending=False)
        st.dataframe(u[["ürün", "yorum", "ortalama_puan", "sikayetli_yorum_payi", "en_sik_sikayet"]]
                     .assign(sikayetli_yorum_payi=u.sikayetli_yorum_payi * 100),
                     hide_index=True, width="stretch",
                     column_config={"ürün": st.column_config.TextColumn(width="large"),
                                    "ortalama_puan": st.column_config.NumberColumn("puan", format="%.1f"),
                                    "sikayetli_yorum_payi": st.column_config.ProgressColumn(
                                        "şikâyetli yorum", format="%.0f%%", min_value=0, max_value=100),
                                    "en_sik_sikayet": "en sık şikâyet"})
        st.caption("En az 3 yorumu olan ürünler.")

# --- Cevap önerici
st.divider()
st.subheader("Müşteri sorusu cevap önerici")
st.caption("Beden, kalıp ve stok bilgisi kodla hesaplanır (F3-04: önerilen beden gerçek satıcı cevaplarıyla %45–50 "
           "tam, %94–96 ±1 beden aynı); Claude yalnızca metni mağazanın üslubunda yazar. Yanlış bedenli taslak "
           "otomatik olarak şablona döner. Taslağı göndermeden önce okuyun.")
anahtar = bool(env_degeri("ANTHROPIC_API_KEY")) and not demo.internet_demosu()
sorular = m.tablolar(veri)["sorular"].dropna(subset=["model_kodu"]).sort_values("soru_tarihi", ascending=False)


def ornegi_al():
    """Yalnızca seçim değişince soruyu ve ürünü doldurur; kullanıcının sonradan yaptığı düzenleme korunur."""
    o = st.session_state.ornek_soru
    if o != "(kendim yazacağım)":
        st.session_state.cevap_soru = o
        st.session_state.cevap_urun = sorular[sorular.soru == o].model_kodu.iloc[0]


st.selectbox("Son sorulardan seç (isteğe bağlı)", ["(kendim yazacağım)"] + sorular.soru.head(30).tolist(),
             key="ornek_soru", on_change=ornegi_al)
soru = st.text_area("Müşteri sorusu", key="cevap_soru", placeholder="ör. 165 boy 58 kilo hangi bedeni almalıyım?")
kodlar = sorted(adlar)
varsayilan = st.session_state.get("cevap_urun")
if varsayilan in kodlar:
    kodlar.remove(varsayilan)
    kodlar.insert(0, varsayilan)
kod = ortak.urun_secimi("Ürün", kodlar, adlar, key=f"cevap_urun_sec_{varsayilan}")
llm = st.toggle("Claude ile yaz (Haiku 5.5, ≈ 0,02 sent)", value=anahtar, disabled=not anahtar,
                help=None if anahtar else ".env dosyasında ANTHROPIC_API_KEY yok; şablon taslak kullanılır.")
if veri == "gercek" and llm:
    st.caption("Soru metni, ürün bilgisi ve mağazanın 3 örnek cevabı Anthropic API'ye gönderilir (müşteri kimliği "
               "gönderilmez).")
if st.button("Taslak oluştur", type="primary", disabled=not soru.strip()):
    from tavsiye.cevap_oner import cevap_oner
    with st.spinner("Taslak hazırlanıyor…"):
        r = cevap_oner(soru, kod, veri, llm=llm)
    b = r["bilgiler"]
    with st.container(border=True):
        st.markdown("**Taslak cevap**")
        st.code(r["cevap"], language=None, wrap_lines=True)
        kaynak = {"llm": "Claude", "sablon": "şablon", "sablon_llm_reddedildi": "şablon (LLM taslağı güvenlik "
                  "kontrolünden geçmedi)"}.get(r["kaynak"], r["kaynak"])
        st.caption(f"Kaynak: {kaynak}" + (f" · maliyet ${r['maliyet_usd']:.4f}" if r["maliyet_usd"] else "")
                   + (" · ⚠️ Bilgiler soruyu tam cevaplamaya yetmeyebilir; göndermeden önce tamamlayın."
                      if r["emin_degil"] else ""))
    with st.expander("Kodla hesaplanan bilgiler"):
        st.markdown(f"- Konu: **{b['konu']}** · boy: {b['boy'] or '—'} · kilo: {b['kilo'] or '—'}\n"
                    f"- Önerilen beden: **{b['setteki_en_yakin'] or '—'}**"
                    + (f" (stokta {'var' if b['onerilen_stokta'] else 'yok'})" if b["setteki_en_yakin"] else "")
                    + f"\n- Kalıp: {b['kalip']['etiket']} ({b['kalip']['beden_iadesi']} beden iadesi)"
                    + (f"\n- Eksik: {', '.join(b['eksik'])}" if b["eksik"] else ""))

ortak.karar_kutusu("Karar", [
    "Şikâyetli ürünlerde en sık konuya göre davranın: beden/kalıp → beden tablosu; kumaş/kalite → tedarikçi; "
    "renk/görsel → fotoğraf.",
    "Beden sorularını cevap önericiyle hızlı cevaplayın; cevap süresi müşteri hizmeti puanını etkiler.",
])
