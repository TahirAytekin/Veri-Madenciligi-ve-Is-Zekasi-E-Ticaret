"""Satıcı paneli (F5): Streamlit çok sayfalı uygulama.

    streamlit run web/app.py

Model çıktıları yoksa önce: python -m web.hazirla
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))       # proje kökü: analiz/, tavsiye/ ... içe aktarılsın

import streamlit as st  # noqa: E402

from web import ortak  # noqa: E402

st.set_page_config(page_title="Satıcı Paneli", page_icon="📊", layout="wide")

SAYFALAR = {
    "Mağaza": [st.Page("sayfalar/genel_bakis.py", title="Genel Bakış", icon="🏠", default=True),
               st.Page("sayfalar/aksiyon_plani.py", title="Aksiyon Planı", icon="✅"),
               st.Page("sayfalar/urunler.py", title="Ürünler", icon="👕")],
    "Şeffaflık": [st.Page("sayfalar/model_dogrulama.py", title="Model Doğrulama", icon="🔬")],
}

ortak.veri_secici()
st.sidebar.divider()
st.sidebar.caption("Sistem yalnızca okur ve önerir; Trendyol'a hiçbir şey yazmaz.")
st.navigation(SAYFALAR).run()
