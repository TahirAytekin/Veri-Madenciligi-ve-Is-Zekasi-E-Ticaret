"""Model ve tahmin kaydı (F2-01). Hepsi ciktilar/ altında; git'e girmez, yeniden üretilir.

    ciktilar/modeller/<model_id>.joblib            eğitilmiş model (yalnızca sahte veriyle eğitilir)
    ciktilar/<veri>/tahminler/<model_id>.csv       tahminler (web, tavsiye motoru ve asistan buradan okur)
"""
import joblib

from hazirlama.ortak import PROJE

CIKTILAR = PROJE / "ciktilar"


def model_kaydet(model, model_id):
    yol = CIKTILAR / "modeller" / f"{model_id}.joblib"
    yol.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, yol)
    return yol


def model_yukle(model_id):
    return joblib.load(CIKTILAR / "modeller" / f"{model_id}.joblib")


def tahmin_kaydet(df, model_id, veri):
    """Tahmin tablosu. Kimlik sütunları (ör. satir_id, model_kodu) ve tahmin sütunları içermelidir."""
    yol = CIKTILAR / veri / "tahminler" / f"{model_id}.csv"
    yol.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(yol, index=False, encoding="utf-8-sig")
    return yol
