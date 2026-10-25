"""Tavsiye şeması (F3-01). Web, asistan ve aksiyon planı bu yapıyı okur.

Her tavsiye: ne görüldü (kanıt), ne yapılmalı (aksiyon), ne kazandırır (aylık TL etkisi ve nasıl hesaplandığı),
ne kadar güvenilir (güven + gerekçe). Güven, dayandığı modelin gerçek veride doğrulama sonucuna bağlıdır
(docs/rapor/02_dogrulama.json): mağazanın kendi gözlenen verisi > gerçekte doğrulanmış model > sınırdaki model.
"""
import json
from dataclasses import asdict, dataclass, field

from hazirlama.ortak import PROJE

GUVEN_PUANI = {"yuksek": 0.9, "orta": 0.6, "dusuk": 0.3}
ONEM_SIRASI = {"yuksek": 0, "orta": 1, "dusuk": 2}
ALANLAR = ("stok", "urun", "iade", "fiyat", "karlilik", "musteri_sesi", "operasyon", "musteri", "kargo", "satis")
DOGRULAMA = PROJE / "docs" / "rapor" / "02_dogrulama.json"


@dataclass
class Tavsiye:
    id: str                      # tekil: "<tür>" veya "<tür>:<model_kodu>"
    tur: str                     # kural adı (kurallar.py)
    alan: str                    # ALANLAR
    baslik: str
    aciklama: str                # ne görüldü, sayılarla
    aksiyon: str                 # satıcının yapacağı somut iş
    kanit: dict                  # {"kaynak": [...], metrik: değer, ...}
    guven: str                   # yuksek, orta, dusuk
    guven_gerekcesi: str
    onem: str = "orta"           # yuksek, orta, dusuk (etkisi TL ile ölçülemeyenlerde sıralama için)
    etki_tl: float | None = None           # aylık beklenen katkı payı farkı (TL, ürün maliyeti hariç)
    etki_aciklama: str = ""                # nasıl hesaplandı + varsayımlar
    varsayimlar: dict = field(default_factory=dict)
    ilgili: dict = field(default_factory=dict)   # {"model_kodu": [...], "kategori": [...]}

    def __post_init__(self):
        assert self.guven in GUVEN_PUANI, self.guven
        assert self.onem in ONEM_SIRASI, self.onem
        assert self.alan in ALANLAR, self.alan

    @property
    def oncelik(self):
        """Beklenen etki × güven (TL). Etkisi ölçülemeyenlerde None."""
        return None if self.etki_tl is None else self.etki_tl * GUVEN_PUANI[self.guven]

    def sozluk(self):
        return {**asdict(self), "oncelik": self.oncelik}


def model_karari(model_id):
    """Doğrulama raporundaki karar: 'basarili', 'basarisiz' veya None (rapor/satır yoksa)."""
    if not DOGRULAMA.exists():
        return None
    satirlar = json.loads(DOGRULAMA.read_text(encoding="utf-8"))["satirlar"]
    return next((s["karar"] for s in satirlar if s["id"] == model_id), None)
