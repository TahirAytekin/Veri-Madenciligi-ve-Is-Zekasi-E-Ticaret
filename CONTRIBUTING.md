# Çalışma Rehberi

Bu proje birden çok kişi tarafından, birbirinin kaldığı yerden devam edilerek geliştiriliyor. Bu rehberin amacı:
herhangi bir ekip üyesinin, hiç kimseye sormadan **"ne yapıldı, nerede kalındı, sırada ne var"** sorularını
cevaplayıp işe başlayabilmesi.

**Okuma sırası (yeni üye):**
1. [README.md](README.md)
2. [docs/DURUM.md](docs/DURUM.md): şu an neredeyiz
3. Bu rehber
4. [docs/PROJE_PLANI.md](docs/PROJE_PLANI.md): görevler
5. [docs/VERI_SOZLUGU.md](docs/VERI_SOZLUGU.md): veri

---

## 1. İlk kurulum

```bash
git clone <depo-adresi>
cd trendyoll
python -m venv .venv
.venv\Scripts\activate            # Windows   (Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python guncelle.py --sahte        # sahte veri için analiz tablolarını üretir (~10 sn)
```

Gerçek veri (`veri/ham`, `veri/gercek`) ve API anahtarları (`.env`) **yalnızca proje sahibinde** bulunur ve GitHub'da
yoktur. Sen sahte veriyle (`veri/sahte`) çalışırsın: aynı tablolar, aynı sütunlar. Yazdığın kod gerçek veride de
değişmeden çalışır; gerçek veride çalıştırma işini proje sahibi yapar.

---

## 2. Günlük çalışma döngüsü

1. `git switch main && git pull`: en güncel hali al.
2. [docs/DURUM.md](docs/DURUM.md) dosyasını ve devralacağın görevin son devir notunu oku.
3. Görevini üstlen (bkz. §3) ve kendi dalında çalış.
4. Küçük ve anlamlı commit'ler at. **Gün sonunda yarım bile olsa push et:** bilgisayarında kalan iş, devralan için yoktur.
5. Görev bitince PR aç, incelemeden sonra birleştir, durum ve devir kayıtlarını güncelle.

---

## 3. Görev üstlenme ve devir

### Üstlenirken
1. [PROJE_PLANI.md](docs/PROJE_PLANI.md) dosyasında bağımlılıkları ✅ olan bir ⬜ görev seç (önce P1).
2. Dal aç: `git switch -c gorev/F2-04-iade-riski`
3. Planda görevin satırına adını yaz, durumu 🟨 yap; [DURUM.md](docs/DURUM.md) → "Aktif görevler" tablosuna satır ekle.
4. Bu değişikliği hemen commit + push et ve **taslak PR** (Draft Pull Request) aç: herkes kimin ne yaptığını görür, aynı işe iki kişi girmez.

### Bırakırken (yarım kalsa da, bitse de)
1. Çalışan son halini commit + push et. Çalışmayan kodu commitliyorsan commit mesajında belirt: `F2-04: (yarım) özellik hazırlama`
2. **Devir notu yaz:** [docs/devir/_SABLON.md](docs/devir/_SABLON.md) dosyasını kopyala →
   `docs/devir/YYYY-AA-GG-<isim>-<görev-id>.md`. Şunları yaz: ne yapıldı, nerede kaldın (dosya / fonksiyon / notebook hücresi),
   devralanın atacağı ilk adım, nasıl çalıştırılır, bilinen sorunlar ve açık sorular.
3. DURUM.md → "Aktif görevler" satırındaki son durumu ve "Son devir notları" listesini güncelle.
4. Görevi bırakıyorsan planda sorumluyu sil, durumu ⬜ yap ve notu "Devredilebilir görevler" altına taşı.

### Devralırken
1. DURUM.md → görevin satırı → son devir notu → taslak PR'ın açıklaması ve yorumları.
2. Dalı al: `git fetch && git switch gorev/F2-04-iade-riski`
3. Devir notundaki "nasıl çalıştırılır" komutunu çalıştır; çalışmıyorsa önce bunu düzelt.
4. Planda ve DURUM.md'de sorumluyu kendin yap; devir notunun sonuna "devralındı: <isim>, <tarih>" ekle.

Devir notları birikerek **projenin günlüğü** olur. Her not ayrı bir dosya olduğu için kimsenin notu başkasınınkiyle çakışmaz.

---

## 4. Dal, commit ve PR kuralları

| | kural | örnek |
|---|---|---|
| Dal | `gorev/<ID>-<kısa-konu>` | `gorev/F1-04-satis-zaman` |
| Commit | `<ID>: <ne yapıldı>`, Türkçe, geçmiş zaman veya emir kipi, tek konu | `F1-04: Haftanın günü ve saat etkisi grafikleri eklendi` |
| PR başlığı | `<ID>: <görev adı>` | `F1-04: Satış ve zaman keşifsel analizi` |
| PR boyutu | bir PR = bir görev (veya bir görevin anlamlı parçası) | |
| İnceleme | en az bir ekip arkadaşının onayı | |
| Birleştirme | **"Create a merge commit"**, squash yok | hoca tüm commit'leri görebilsin |

`main` dalına doğrudan push yapılmaz; her değişiklik PR ile gelir.

---

## 5. Kod kuralları

- **İsimlendirme Türkçe** ve mevcut kodla tutarlı olmalı (`siparisler`, `iade_orani`, `kesim_uygula`).
- **Bölüm başlıkları** mevcut stilde yazılır:
  ```python
  # ====================================================
  # 1) BÖLÜM ADI
  # ====================================================
  ```
- Her modülün başında ne yaptığını anlatan kısa bir docstring olur.
- **Veri yolları** `hazirlama/ortak.py` içindeki `VERI`, `HAM` sabitlerinden alınır; `C:\Users\...` gibi sabit yol yazılmaz.
- Her betik ve fonksiyon `veri="sahte" | "gercek"` ile iki veri setinde de çalışır.
- **Metrik hesapları** yalnızca `analiz/metrikler.py` içinde yapılır; web, tavsiye ve asistan oradan çağırır.
- **Rastgelelik** sabit tohumla (`random_state=42`); sonuçlar tekrarlanabilir olmalı.
- Model eğitiminde `analiz/` değil, **kesimli** tablolar kullanılır (`ozellik_cikar.py --kesim`; bkz. [MODEL_DOGRULAMA.md](docs/MODEL_DOGRULAMA.md)).
- Yeni paket eklersen `requirements.txt` dosyasına ekle ve PR'da belirt.

---

## 6. Notebook kuralları

- Konum ve ad: `notebooks/<faz>/<görev-id>_<konu>.ipynb` (ör. `notebooks/faz1/F1-04_satis_zaman.ipynb`).
- **Yalnızca sahte veriyle çalıştırılmış çıktılar commitlenir.** Gerçek veriyle çalıştırdığın notebook'un çıktısını
  committen önce temizle (`nbstripout` veya Jupyter'de "Clear All Outputs"): çıktılarda gerçek veri görünür.
- Notebook keşif içindir. Tekrar kullanılacak kod (metrik, özellik, model) `analiz/` veya `modeller/` içine taşınır.
- Notebook'un başında amaç, sonunda **bulgular** bölümü olur; bulgular Faz 1 özet raporuna ve tavsiyelere girdi olur.

---

## 7. Veri ve güvenlik kırmızı çizgileri

Aşağıdakiler **asla** commitlenmez (`.gitignore` engeller; yine de `git status` ile kontrol et):

| dosya / klasör | neden |
|---|---|
| `.env` | API anahtarları |
| `veri/ham/`, `veri/gercek/` | gerçek mağaza verisi |
| `ciktilar/gercek/`, `veri/gercek/etiketler/` | gerçek veriden üretilen sonuçlar |
| gerçek veri çıktısı içeren notebook | veri sızıntısı |

Ayrıca:
- Gerçek veri buluta yüklenmez: Colab, ChatGPT veya başka bir site yok.
- Bir anahtar veya gerçek veri yanlışlıkla push edildiyse: **hemen proje sahibine haber ver.** Anahtar panelden yenilenir. Dosyayı sonradan silmek yetmez, git geçmişinde kalır.

---

## 8. Bitti tanımı

Bir görev ancak şunlar sağlandığında ✅ olur:

**Her görev için**
- [ ] Kod sahte veriyle baştan sona hatasız çalışıyor; çalıştırma komutu PR'da yazılı
- [ ] Varsa testler yazıldı ve geçiyor
- [ ] PR incelendi ve birleştirildi
- [ ] Plan ve DURUM.md güncellendi

**Analiz görevi (Faz 1)**
- [ ] Notebook baştan sona çalışıyor, "Bulgular" bölümü var
- [ ] Kullanılan metrikler `analiz/metrikler.py` üzerinden hesaplanıyor

**Model görevi (Faz 2–3)**
- [ ] Baseline ile karşılaştırıldı ([MODEL_DOGRULAMA.md](docs/MODEL_DOGRULAMA.md))
- [ ] Seviye 1 (sahte veri doğru cevapları) ve seviye 2 (kesimli zaman testi) sonuçları model kartında
- [ ] Model kartı `docs/modeller/<ID>.md`: amaç, veri, özellikler, model, metrikler, sınırlar
- [ ] Tahminler standart formatta `ciktilar/<veri>/` altında
- [ ] Gerçek veride çalıştırılması proje sahibine devredildi (devir notunda komutla)

**Web görevi (Faz 6)**
- [ ] Sayfa sahte veriyle çalışıyor; sayılar kod içine yazılmamış, `analiz/` ve `ciktilar/` içinden geliyor
- [ ] Ekran görüntüsü PR'da

**Asistan görevi (Faz 5)**
- [ ] Değerlendirme seti çalıştırıldı, sonuç ve maliyet PR'da

---

## 9. İnceleme kontrol listesi (PR'ı inceleyen için)

- Yasaklı dosya var mı? (§7)
- Kod sahte veriyle çalışıyor mu? Komutu kendin çalıştır.
- Sızıntı var mı? Model, kesimden sonraki bilgiyi kullanıyor mu?
- Metrik `analiz/metrikler.py` dışında yeniden hesaplanmış mı?
- Devir notu ve DURUM.md güncel mi?

---

## 10. Yapay zekâ araçlarının kullanımı

Yapay zekâ araçları (ör. Claude Code) kullanılabilir. Yine de:
- Yazılan kodu anladığından ve çalıştırıp doğruladığından emin ol: PR'ı açan kişi koddan sorumludur.
- Yapay zekâ ile birlikte yazılan commit'lerde `Co-Authored-By:` satırı bulunur; bu, yardım alındığını şeffafça gösterir.
- Okulunun yapay zekâ kullanım kurallarına uy ve gerekiyorsa hocana beyan et.
- Yapay zekâ asistanları için proje özeti [CLAUDE.md](CLAUDE.md) dosyasındadır.
