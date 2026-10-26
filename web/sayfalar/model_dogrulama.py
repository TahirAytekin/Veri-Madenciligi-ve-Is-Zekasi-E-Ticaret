"""Model Doğrulama (F5-10): sahte veriyle eğitilen modellerin gerçek verideki sonucu, referansla fark, sınırlar.

Kaynak: docs/rapor/02_dogrulama.json (python -m modeller.dogrulama_raporu). Bu sayfa iki veri seti için de aynıdır:
modeller sahteyle eğitilip gerçekle test edildi.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from web import ortak

d = ortak.dogrulama()
satirlar = d["satirlar"]

st.title("Model Doğrulama")
st.caption(f"Tüm modeller yalnızca sahte veriyle eğitildi; gerçek veri yalnızca test için kullanıldı (test dönemi "
           f"{ortak.donem_metni(d['test_donemi'])}). Tasarım ve başarı ölçütü her modelde eğitimden önce yazıldı.")

basarili = [s for s in satirlar if s["karar"] == "basarili"]
k1, k2, k3 = st.columns(3)
k1.metric("Test edilen model", len(satirlar))
k2.metric("Gerçekte referansı anlamlı geçen", len(basarili))
k3.metric("Geçemeyen", len(satirlar) - len(basarili))
st.info("**Başarı** = model, eğitim gerektirmeyen en güçlü basit yöntemi (referans) gerçek veride geçiyor ve farkın "
        "%95 güven aralığı 0'ın doğru tarafında. Geçemeyen modellerde web'de referans kullanılır; bu bir hata değil, "
        "ölçülmüş bir bulgudur.")

# --- Sonuç tablosu
t = pd.DataFrame([{
    "görev": s["id"], "soru": s["soru"], "ölçüt": s["metrik"], "model": s["gercek_model"],
    "referans": f"{s['referans_adi']}: {s['gercek_referans']:.3f}".replace(".", ","),
    "fark [%95 GA]": f"{s['fark']:+.3f} [{s['alt']:+.3f}, {s['ust']:+.3f}]".replace(".", ","),
    "karar": "✅ başarılı" if s["karar"] == "basarili" else "✗ geçemedi", "web'de": s["web"],
} for s in satirlar])
st.dataframe(t, hide_index=True, width="stretch",
             column_config={"model": st.column_config.NumberColumn(format="%.3f"),
                            "soru": st.column_config.TextColumn(width="medium"),
                            "web'de": st.column_config.TextColumn(width="large")})
st.caption("WAPE'de (talep) düşük değer iyidir; farkın 0'ın altında olması model lehinedir. Diğer ölçütlerde yüksek "
           "değer iyidir.")

# --- Fark grafiği
st.subheader("Model − referans farkı (gerçek veri, %95 güven aralığı)")
fig = go.Figure()
for s in satirlar:
    iyi_yon = 1 if s["yon"] == "yuksek_iyi" else -1                    # grafikte sağ her zaman model lehine
    f, a, u = (x * iyi_yon for x in (s["fark"], s["alt"], s["ust"]))
    a, u = min(a, u), max(a, u)
    renk = ortak.DURUM_RENK["iyi"] if s["karar"] == "basarili" else "#8a8a8a"
    fig.add_trace(go.Scatter(x=[f], y=[f"{s['id']} · {s['ad']}"], mode="markers",
                             marker=dict(size=11, color=renk),
                             error_x=dict(type="data", symmetric=False, array=[u - f], arrayminus=[f - a], color=renk,
                                          thickness=2, width=6),
                             showlegend=False,
                             hovertemplate=f"{s['id']}: fark {f:+.3f} [{a:+.3f}, {u:+.3f}]<extra></extra>"))
fig.add_vline(x=0, line=dict(width=1, color="gray"))
fig.update_xaxes(title="← referans daha iyi · model daha iyi →")
fig.update_yaxes(autorange="reversed")
st.plotly_chart(ortak.tema(fig, 60 + 42 * len(satirlar)), width="stretch")
st.caption("Yeşil: aralık tamamen 0'ın sağında (başarılı). Gri: aralık 0'ı içeriyor ya da solunda. WAPE'li görevde "
           "işaret çevrildi.")

# --- Ayrıntı
st.subheader("Model ayrıntısı")
sec = st.selectbox("Görev", [s["id"] for s in satirlar],
                   format_func=lambda i: next(f"{s['id']} · {s['ad']}" for s in satirlar if s["id"] == i))
s = next(x for x in satirlar if x["id"] == sec)
sol, sag = st.columns(2)
with sol:
    st.markdown(f"**Soru:** {s['soru']}  \n**Yöntem:** {s['yontem']}  \n**Web'de:** {s['web']}")
    if s.get("not"):
        st.caption(s["not"])
    st.markdown(f"[Model kartı]({s['kart']}) (depoda: `{s['kart']}`)")
with sag:
    s1 = s.get("seviye1") or {}
    if s1:
        st.markdown("**Seviye 1 — sahte veride gizli doğru cevapla:**")
        st.markdown(" · ".join(f"{k}: {v:.3f}".replace(".", ",") for k, v in s1.items() if v is not None))
    if s.get("tohumlar"):
        tt = pd.DataFrame(s["tohumlar"]).T.rename_axis("tohum").reset_index()
        st.markdown("**Üç sahte veri tohumunda gerçek sonuç:**")
        st.dataframe(tt, hide_index=True, width="stretch",
                     column_config={c: st.column_config.NumberColumn(format="%.3f")
                                    for c in ("model", "referans", "fark", "alt", "ust")})

with st.expander("Yorum: bütün modellerden çıkan dersler"):
    st.markdown(ortak.dogrulama_yorumu())

ortak.karar_kutusu("Bu sonuçlar web'de nasıl kullanılıyor?", [
    "Gerçekte doğrulanan beden önerisi (F2-04C, F3-04) beden önericide ve soru cevaplarında kullanılır.",
    "İade riski için ürünün kendi geçmiş iade oranı, stok için geçen haftanın satış hızı kullanılır: modeller bu "
    "basit referansları gerçek veride geçemedi.",
    "Her tavsiyenin güven düzeyi bu tablodaki karara bağlıdır (Aksiyon Planı).",
])
