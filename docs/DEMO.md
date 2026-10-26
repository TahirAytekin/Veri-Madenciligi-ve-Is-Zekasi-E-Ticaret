# İnternet demosu (F5-12)

Panelin, **tamamen sahte bir mağazanın verisiyle**, herkese açık bir bağlantıdan çalışan sürümü. Hoca veya jüri
kurulum yapmadan açıp gezebilir.

## Demoda ne var, ne yok
| | durum | neden |
|---|---|---|
| 9 sayfanın tamamı (Genel Bakış … Model Doğrulama) | ✓ | sahte veriyle |
| Beden önerici, senaryo simülatörü, haftalık PDF rapor | ✓ | kodla hesaplanır |
| Müşteri Sesi (yorum analizi) | ✓ | sahte veri sonuçları depoda hazır (`web/demo_ciktilar/`); BERT çalıştırılmaz |
| Cevap önerici | şablonla | Claude kapalı |
| **Asistan** | **kapalı** | Her soru ücretli bir API çağrısıdır; demoya anahtar konursa bağlantıyı bilen herkes anahtarı kullanır |
| Gerçek mağaza verisi | **yok** | gerçek veri GitHub'da yoktur ve olmayacaktır |

**Teknik ayrıntılar:**
- Demo yalnızca hafif paketlerle çalışır (`web/requirements.txt`: PyTorch, transformers, sentence-transformers yok).
- Yerel ölçümde en yüksek bellek 333 MB, ilk açılış ~30 saniye. İlk açılışta iki model sahte veriyle eğitilir ve çıktılar üretilir; sonraki açılışlar hızlıdır.
- Her PR'da GitHub Actions'taki **"İnternet demosu"** işi aynı kurulumu yapıp 9 sayfayı açar (`.github/demo_kontrol.py`).

## Yayına alma (Streamlit Community Cloud, ücretsiz)
Bu adımları depo sahibi yapar. Demo herkese açık olur ama içinde yalnızca GitHub'da zaten herkese açık olan sahte veri bulunur.

1. https://share.streamlit.io adresine git ve **GitHub hesabınla** giriş yap. İlk girişte Streamlit, GitHub depolarına erişim izni ister.
2. **Create app** → **Deploy a public app from GitHub**.
3. Alanları şöyle doldur:
   - **Repository:** `TahirAytekin/Veri-Madenciligi-ve-Is-Zekasi-E-Ticaret`
   - **Branch:** `main`
   - **Main file path:** `web/app.py`
   - **App URL:** istediğin kısa ad (ör. `trendyol-satici-paneli`)
4. **Advanced settings**:
   - **Python version:** 3.14 (listede yoksa en yenisi).
   - **Secrets** kutusuna yalnızca şunu yaz:
     ```toml
     DEMO = "1"
     ```
     **`ANTHROPIC_API_KEY` ve `.env`'deki hiçbir değeri buraya yazma.**
5. **Deploy**'a tıkla. İlk kurulum paketlerle birlikte birkaç dakika sürer, sonra ilk açılışta ~30 saniye "Demo hazırlanıyor" yazar.
6. Açılınca sol menüde "**Demo:** tamamen sahte bir mağazanın verisi" notunu gör. Bağlantıyı README'ye ekle.

**Güncelleme:** `main`'e her birleştirmede Streamlit Cloud demoyu kendiliğinden yeniden kurar.

## Bilinen risk
`.streamlit/config.toml`'da `server.address = "localhost"` var; gerçek verinin yerel ağa açılmaması için. Streamlit Cloud sunucu adresini kendisi yönetir ve bu ayarın orada sorun çıkarması beklenmez. Ama ilk yayında denenmedi. Demo açılmazsa (sürekli "Please wait…") bu ayar sorumlu olabilir: hata günlüğünü (Manage app → Logs) paylaş, düzeltelim.

## Yerelde denemek
```bash
python -m venv .venv-demo && .venv-demo\Scripts\activate
pip install -r web/requirements.txt
set DEMO=1            # PowerShell: $env:DEMO = "1"
python .github/demo_kontrol.py              # 9 sayfa, hatasız olmalı
python -m streamlit run web/app.py
```
