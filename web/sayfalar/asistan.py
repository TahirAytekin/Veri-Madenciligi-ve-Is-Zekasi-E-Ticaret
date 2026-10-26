"""Asistan (F5-09): mağazanın verisiyle sohbet (asistan/sohbet.py). Sayılar araçlardan gelir; kullanılan araçlar
ve girdileri her cevabın altında gösterilir."""
import json

import plotly.graph_objects as go
import streamlit as st

from hazirlama.ortak import env_degeri
from web import ortak

veri = st.session_state.veri
MODELLER = {"claude-haiku-5-5": "Haiku 5.5 (varsayılan, ≈ 0,08 sent/soru)",
            "claude-opus-5-5": "Opus 5.5 (≈ 2 sent/soru)"}
ORNEKLER = ["Bu hafta ilk ne yapmalıyım?", "İade oranı en yüksek kategori hangisi?",
            "Son 30 günde net satışım önceki 30 güne göre nasıl?", "Kalıbı dar olan ürünlerim hangileri?",
            "Beden iadelerini %30 azaltırsam ayda ne kazanırım?", "Son 6 ayın net satışını aylık grafikte göster"]
ARAC_ADI = {"metrik_hesapla": "metrik", "sql_sorgula": "SQL", "tablo_semasi": "tablo şeması",
            "tahmin_getir": "model çıktısı", "urun_karti": "ürün kartı", "tavsiyeleri_getir": "tavsiyeler",
            "senaryo_calistir": "senaryo", "beden_oner": "beden önerisi", "bilgi_ara": "bilgi tabanı",
            "grafik_ciz": "grafik"}

st.title("Asistan")
st.caption("Mağazanın kendi verisiyle konuşun. Sayılar her zaman araçlarla hesaplanır (metrik, SQL, senaryo …); "
           "tanımlar ve 'neden' soruları bilgi tabanından aranır. Değerlendirme: 32 soruda Haiku %96,9, Opus %100 "
           "(F4-05). Asistan yalnızca okur; veriyi değiştiremez.")

if not env_degeri("ANTHROPIC_API_KEY"):
    st.warning("`.env` dosyasında `ANTHROPIC_API_KEY` yok; asistan çalışmaz. Diğer sayfalar anahtarsız çalışır.")
    st.stop()

sol, sag = st.columns([2, 1])
model = sol.selectbox("Model", list(MODELLER), format_func=MODELLER.get)
if veri == "gercek":
    sol.caption("Gerçek veri: araç sonuçları (satış rakamları, yorum metinleri) Anthropic API'ye gönderilir; müşteri "
                "kimlikleri anonimdir.")

anahtar = f"sohbet_{veri}_{model}"
if anahtar not in st.session_state:
    st.session_state[anahtar] = {"turlar": [], "mesajlar": None, "maliyet": 0.0}
sohbet = st.session_state[anahtar]
maliyet_alani = sag.empty()
maliyet_alani.metric("Bu sohbetin maliyeti", f"${sohbet['maliyet']:.4f}")
if sag.button("Yeni sohbet"):
    st.session_state[anahtar] = {"turlar": [], "mesajlar": None, "maliyet": 0.0}
    st.rerun()


@st.cache_resource
def asistan(veri, model, surum):            # surum: veri yenilenince yeni asistan (araç önbellekleri de temizlenir)
    from asistan.sohbet import Asistan
    return Asistan(veri, model)


def grafikler(cagrilar):
    """grafik_ciz aracının ürettiği grafikler (veri panelde; modele yalnızca özet gitti)."""
    for c in cagrilar:
        g = c.get("grafik")
        if not g:
            continue
        ek = f" {g['birim']}" if g["birim"] and g["birim"] != "%" else ""
        hover = f"%{{x}}: %{{y:,.1f}}{'%' if g['birim'] == '%' else ek}<extra></extra>"
        if g["tur"] == "cizgi":
            fig = go.Figure(go.Scatter(x=g["x"], y=g["y"], mode="lines+markers", hovertemplate=hover,
                                       line=dict(width=2, color=ortak.SERI[0]), marker=dict(size=7)))
            fig.update_layout(title=dict(text=g["baslik"], font=dict(size=14)))
            fig = ortak.tema(fig, 320)
        else:
            fig = ortak.cubuk(g["x"], g["y"], g["baslik"], yatay=g["tur"] == "yatay_cubuk", hover=hover,
                              yukseklik=max(320, 26 * len(g["x"])) if g["tur"] == "yatay_cubuk" else 320)
        sonek = "%" if g["birim"] == "%" else ek
        if g["tur"] == "yatay_cubuk":
            fig.update_xaxes(ticksuffix=sonek)
        else:
            fig.update_yaxes(ticksuffix=sonek)
        st.plotly_chart(fig, width="stretch")
        if g.get("not"):
            st.caption(f"⚠️ {g['not']}")


def araclar_ozeti(cagrilar):
    with st.expander(f"Kullanılan araçlar ({len(cagrilar)})" if cagrilar else "Araç kullanılmadı"):
        for c in cagrilar:
            durum = " ⚠️ hata" if c.get("hata") else ""
            st.markdown(f"**{ARAC_ADI.get(c['ad'], c['ad'])}**{durum} · `{c['ad']}`")
            st.code(json.dumps(c["girdi"], ensure_ascii=False), language="json", wrap_lines=True)


# --- Geçmiş
for t in sohbet["turlar"]:
    with st.chat_message("user"):
        st.markdown(t["soru"])
    with st.chat_message("assistant"):
        st.markdown(t["cevap"])
        grafikler(t["araclar"])
        araclar_ozeti(t["araclar"])
        st.caption(f"{t['sure_sn']} sn · ${t['maliyet_usd']:.4f}")

# --- Yeni soru
if not sohbet["turlar"]:
    st.markdown("**Örnek sorular:**")
    kolonlar = st.columns(3)
    for i, o in enumerate(ORNEKLER):
        if kolonlar[i % 3].button(o, key=f"ornek_{i}", width="stretch"):
            st.session_state.bekleyen_soru = o
            st.rerun()

soru = st.chat_input("Sorunuzu yazın…") or st.session_state.pop("bekleyen_soru", None)
if soru:
    with st.chat_message("user"):
        st.markdown(soru)
    with st.chat_message("assistant"):
        alan, parcalar = st.empty(), []

        def akis(metin):
            parcalar.append(metin)
            alan.markdown("".join(parcalar) + "▌")

        with st.spinner("Veriye bakılıyor…"):
            try:
                y = asistan(veri, model, ortak._surum(veri)).sor(soru, gecmis=sohbet["mesajlar"], akis=akis)
            except Exception as e:                                       # noqa: BLE001 — kullanıcıya göster
                alan.empty()
                st.error(f"Asistan cevap veremedi: {type(e).__name__}: {e}")
                st.stop()
        alan.markdown(y["cevap"])
        grafikler(y["araclar"])
        araclar_ozeti(y["araclar"])
        st.caption(f"{y['sure_sn']} sn · ${y['maliyet_usd']:.4f}")
    sohbet["turlar"].append({"soru": soru, "cevap": y["cevap"], "araclar": y["araclar"], "sure_sn": y["sure_sn"],
                             "maliyet_usd": y["maliyet_usd"]})
    sohbet["mesajlar"] = y["mesajlar"]
    sohbet["maliyet"] += y["maliyet_usd"] or 0
    maliyet_alani.metric("Bu sohbetin maliyeti", f"${sohbet['maliyet']:.4f}")

ortak.karar_kutusu("İpuçları", [
    "Dönem belirtin (\"son 30 günde\"); belirtmezseniz son 90 gün kullanılır.",
    "Bir tavsiyenin nedenini sorun: \"stok tükenme tavsiyesini neden verdin?\"",
    "Cevaptaki her sayının hangi araçtan geldiğini 'Kullanılan araçlar' altında görebilirsiniz.",
])
