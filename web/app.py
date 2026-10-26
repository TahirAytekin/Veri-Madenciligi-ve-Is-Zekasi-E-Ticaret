"""Satıcı paneli (F5): Streamlit çok sayfalı uygulama.

    streamlit run web/app.py

Panel çıktıları yoksa önce: python calistir.py (günlük: python guncelle.py)
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
    "Analiz ve araçlar": [st.Page("sayfalar/iade_beden.py", title="İade ve Beden", icon="📏"),
                          st.Page("sayfalar/talep_stok.py", title="Talep ve Stok", icon="📦"),
                          st.Page("sayfalar/finans_senaryo.py", title="Finans ve Senaryo", icon="💰"),
                          st.Page("sayfalar/musteri_sesi.py", title="Müşteri Sesi", icon="💬")],
    "Asistan": [st.Page("sayfalar/asistan.py", title="Asistan", icon="🤖")],
    "Şeffaflık": [st.Page("sayfalar/model_dogrulama.py", title="Model Doğrulama", icon="🔬")],
}

ortak.veri_secici()
st.sidebar.divider()
st.sidebar.caption("Sistem yalnızca okur ve önerir; Trendyol'a hiçbir şey yazmaz.")
st.navigation(SAYFALAR).run()
