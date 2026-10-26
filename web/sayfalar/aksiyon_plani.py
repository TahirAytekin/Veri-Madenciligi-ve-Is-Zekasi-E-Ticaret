"""Aksiyon Planı (F5-03): haftalık plan, tüm tavsiyeler (filtreli), beklenen kazanç, "yapıldı" işareti, indirme."""
import json

import pandas as pd
import streamlit as st

from modeller.ortak.degerlendir import CIKTILAR
from web import ortak
from web.ortak import tl

veri = st.session_state.veri
_, (tavsiyeler, hatalar, plan), _ = ortak.yukle(veri)
YAPILANLAR = CIKTILAR / veri / "yapilanlar.json"


def yapilanlar():
    try:
        return set(json.loads(YAPILANLAR.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return set()


def isaretle(tid):
    s = yapilanlar()
    s.symmetric_difference_update({tid})
    YAPILANLAR.parent.mkdir(parents=True, exist_ok=True)
    YAPILANLAR.write_text(json.dumps(sorted(s), ensure_ascii=False), encoding="utf-8")


st.title("Aksiyon Planı")
st.caption("Öncelik = beklenen aylık katkı payı × güven. Etkiler ürün maliyeti hariç ve kısmen örtüşür; toplamı üst "
           "sınırdır. Kurallar: docs/TAVSIYE_KURALLARI.md")
ortak.eksik_uyarisi(veri)
if hatalar:
    st.warning("Bazı kurallar çalışmadı: " + ", ".join(hatalar))

yapildi = yapilanlar()
a = plan["aksiyonlar"]
k1, k2, k3, k4 = st.columns(4)
k1.metric("Tavsiye", len(tavsiyeler))
k2.metric("Bu haftanın planı", len(a))
k3.metric("Planın aylık etkisi (üst sınır)", tl(plan["toplam_aylik_etki_tl"]))
k4.metric("Yapıldı", f"{sum(x['id'] in yapildi for x in a)} / {len(a)}")

# --- Haftalık plan
st.subheader("Bu haftanın planı")
for x in a:
    with st.container(border=True):
        sol, sag = st.columns([0.08, 0.92])
        sol.checkbox("yapıldı", value=x["id"] in yapildi, key=f"yap_{x['id']}", label_visibility="collapsed",
                     on_change=isaretle, args=(x["id"],))
        etki = f"**{tl(x['etki_tl'])}/ay**" if x["etki_tl"] is not None else "etki ölçülmedi"
        ustu = "~~" if x["id"] in yapildi else ""
        sag.markdown(f"{ustu}**{x['sira']}. {x['baslik']}**{ustu} · {etki} · güven "
                     f"{ortak.GUVEN_ETIKET[x['guven']]}  \n↳ {x['aksiyon']}")
        with sag.expander("Kanıt ve hesap"):
            st.write(x["aciklama"])
            if x["etki_aciklama"]:
                st.caption(f"Etki: {x['etki_aciklama']}")
            st.caption(f"Güven: {x['guven_gerekcesi']}")
            if x["varsayimlar"]:
                st.caption("Varsayımlar: " + ", ".join(f"{k} = {v}" for k, v in x["varsayimlar"].items()))
            kaynak = x["kanit"].get("kaynak", [])
            if kaynak:
                st.caption("Kaynak: " + ", ".join(kaynak))

# --- Tüm tavsiyeler
st.divider()
st.subheader("Tüm tavsiyeler")
t = pd.DataFrame(tavsiyeler)
sol, orta, sag = st.columns(3)
alanlar = sol.multiselect("Alan", sorted(t.alan.unique()))
guvenler = orta.multiselect("Güven", ["yuksek", "orta", "dusuk"], format_func=ortak.GUVEN_ETIKET.get)
yalniz_olculen = sag.toggle("Yalnızca etkisi ölçülenler")
s = t[ortak.filtre(t.alan, alanlar) & ortak.filtre(t.guven, guvenler)]
if yalniz_olculen:
    s = s[s.etki_tl.notna()]
tablo = pd.DataFrame({"tavsiye": s.baslik, "aksiyon": s.aksiyon, "aylık etki (TL)": s.etki_tl.round(0),
                      "güven": s.guven.map(ortak.GUVEN_ETIKET), "önem": s.onem, "alan": s.alan,
                      "yapıldı": s.id.isin(yapildi)})
st.dataframe(tablo, hide_index=True, width="stretch",
             column_config={"aylık etki (TL)": st.column_config.NumberColumn(format="%,.0f"),
                            "aksiyon": st.column_config.TextColumn(width="large")})
st.caption(f"{len(s)} tavsiye gösteriliyor.")

# --- İndir
plan_metni = "\n".join([f"# Haftalık aksiyon planı ({veri})", ""] + [
    f"{x['sira']}. [{'x' if x['id'] in yapildi else ' '}] {x['baslik']} — "
    f"{tl(x['etki_tl']) + '/ay' if x['etki_tl'] is not None else 'etki ölçülmedi'}\n   {x['aksiyon']}" for x in a])
sol, sag = st.columns(2)
sol.download_button("Planı indir (.md)", plan_metni, file_name=f"aksiyon_plani_{veri}.md", mime="text/markdown")
sag.download_button("Tüm tavsiyeleri indir (.csv)", tablo.to_csv(index=False).encode("utf-8-sig"),
                    file_name=f"tavsiyeler_{veri}.csv", mime="text/csv")

ortak.karar_kutusu("Karar", [
    "Planı yukarıdan aşağıya uygulayın; tamamlananları işaretleyin (bu bilgisayarda saklanır).",
    "Etkisi ölçülmeyen tavsiyeler (şikâyet, sezon, çapraz satış) TL ile sıralanamaz; plana ayrı yer verilir.",
    "Bir tavsiyenin nedenini sormak için Asistan'ı kullanın: \"…tavsiyesini neden verdin?\"",
])
