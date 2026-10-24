"""Ortam kontrolü (F0-02): paketler kurulu mu, temel işlemler çalışıyor mu, hazır modeller iniyor mu?

    python -m pytest tests/test_ortam.py                     # hızlı kontroller
    AGIR_TESTLER=1 python -m pytest tests/test_ortam.py      # + hazır modelleri indirip dener (~900 MB ilk seferde)
"""
import importlib

import numpy as np
import pytest

PAKETLER = ["numpy", "pandas", "requests", "duckdb", "sklearn", "lightgbm", "torch", "transformers",
            "sentence_transformers", "streamlit", "plotly", "anthropic"]

DUYGU_MODELI = "savasy/bert-base-turkish-sentiment-cased"      # F2-06
EMBEDDING_MODELI = "intfloat/multilingual-e5-small"           # F4-02


@pytest.mark.parametrize("paket", PAKETLER)
def test_paket_kurulu(paket):
    importlib.import_module(paket)


def test_torch_hesaplama():
    import torch
    x = torch.randn(64, 8)
    katman = torch.nn.Linear(8, 1)
    kayip = katman(x).pow(2).mean()
    kayip.backward()
    assert katman.weight.grad is not None


def test_lightgbm_egitim():
    import lightgbm as lgb
    rng = np.random.default_rng(0)
    X = rng.normal(size=(200, 3))
    y = (X[:, 0] + rng.normal(scale=0.1, size=200) > 0).astype(int)
    model = lgb.LGBMClassifier(n_estimators=20, verbose=-1).fit(X, y)
    assert model.score(X, y) > 0.9


def test_duckdb_sahte_veri():
    import duckdb
    from ortak import VERI
    yol = (VERI / "sahte" / "siparisler.csv").as_posix()
    # DuckDB 2.0: ilişkilerde fetchone() kaldırıldı, fetchall() kullanılır
    adet = duckdb.sql(f"SELECT COUNT(*) FROM read_csv_auto('{yol}')").fetchall()[0][0]
    assert adet > 1000


@pytest.mark.agir
def test_turkce_duygu_modeli():
    from transformers import pipeline
    duygu = pipeline("sentiment-analysis", model=DUYGU_MODELI)
    assert duygu("kumaşı çok kaliteli, tam beklediğim gibi")[0]["label"] == "positive"
    assert duygu("defolu geldi, bir daha almam")[0]["label"] == "negative"


@pytest.mark.agir
def test_embedding_modeli():
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(EMBEDDING_MODELI)
    v = model.encode(["passage: kargo çok hızlı geldi", "passage: kumaş kalitesi düşük"], normalize_embeddings=True)
    assert v.shape == (2, 384)
    assert np.allclose(np.linalg.norm(v, axis=1), 1, atol=1e-3)
