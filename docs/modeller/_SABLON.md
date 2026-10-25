# Model kartı — <ID>: <model adı>

<!-- Bu dosyayı kopyala: docs/modeller/<ID>.md. Sayıları ciktilar/<veri>/dogrulama/<ID>.json'dan al. -->

**Görev:** <ID> · **Yazan:** <isim> · **Tarih:** <YYYY-AA-GG> · **Kod:** `modeller/<dosya>.py`

## Amaç
<!-- Bu model satıcıya hangi kararı aldırıyor? Hangi tavsiye / sayfa kullanıyor? -->

## Veri
| | |
|---|---|
| Eğitim | sahte veri, <tarih aralığı>, <n> satır |
| Hiperparametre seçimi | sahtenin son 90 günü |
| Test | gerçek veri, <tarih aralığı>, <n> satır (eğitimde hiç kullanılmadı) |
| Hedef | <hedef ve tanımı> |

## Özellikler
<!-- modeller/ortak/ozellikler.py'deki hangi özellikler; neden; dışarıda bırakılanlar ve nedeni -->

## Model
<!-- Algoritma, önemli hiperparametreler, neden seçildi -->

## Sonuçlar

### Seviye 1 — sahte veride doğru cevap kontrolü
<!-- dogru_cevaplar/ ile karşılaştırma: model gizli gerçeği bulabildi mi? -->

### Seviye 2 — gerçek veride test
| skor | ROC-AUC | PR-AUC | Brier | ortalama tahmin | gerçekleşen oran |
|---|---|---|---|---|---|
| model | | | | | |
| baseline: kategori geçmişi | | | | | |
| baseline: model geçmişi | | | | | |

<!-- Kalibrasyon: tahmin edilen ile gerçekleşen oran dilimlerde tutuyor mu? -->

## Sınırlar ve riskler
<!-- Gerçek veride nerede zayıf; hangi durumda kullanılmamalı; sahte–gerçek farkının etkisi -->

## Nasıl çalıştırılır
```bash
python -m modeller.<dosya>
```
