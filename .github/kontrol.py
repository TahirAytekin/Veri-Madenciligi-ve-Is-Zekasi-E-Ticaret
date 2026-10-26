"""Yasaklı dosya ve gizli bilgi kontrolü (F0-05). GitHub Actions her PR'da çalıştırır; push etmeden önce yerelde de:

    python .github/kontrol.py

Yalnızca git'e eklenmiş (izlenen) dosyalara bakar ve yalnızca standart kütüphaneyi kullanır.
    1. yasaklı yollar: .env, gerçek/ham veri, ciktilar/, loglar/, deney sahte verileri, model dosyaları
    2. dosya boyutu: 20 MB üstü
    3. içerik: Anthropic anahtarı, dolu TRENDYOL_API_* / MUSTERI_ID_TUZ / ANTHROPIC_API_KEY atamaları, özel anahtar
    4. yerelde .env varsa: içindeki gizli değerlerin hiçbiri izlenen bir dosyada geçmemeli (değerler yazdırılmaz)
Sorun bulunursa çıkış kodu 1; ne bulunduğu dosya ve kural adıyla yazılır, gizli değerin kendisi asla yazılmaz.
"""
import re
import subprocess
import sys
from pathlib import Path

PROJE = Path(__file__).resolve().parents[1]
EN_BUYUK_MB = 20
YASAKLI_YOL = [
    (r"(^|/)\.env$", ".env (gizli anahtarlar)"),
    (r"^veri/(ham|gercek)/", "gerçek veya ham veri"),
    (r"^veri/sahte_(t|v1|v3)", "yeniden üretilebilir deney verisi"),
    (r"^ciktilar/", "üretilen çıktılar (gerçek veriye ait olabilir)"),
    (r"^loglar/", "günlük kayıtları"),
    (r"\.(joblib|npy|pkl|pt|safetensors)$", "model veya vektör dosyası"),
]
ICERIK = [
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"), "Anthropic API anahtarı"),
    (re.compile(r"^\s*(TRENDYOL_API_KEY|TRENDYOL_API_SECRET|MUSTERI_ID_TUZ|ANTHROPIC_API_KEY)\s*=\s*\S", re.M),
     "dolu gizli değişken ataması"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "özel anahtar"),
]
METIN_UZANTILARI = {".py", ".md", ".txt", ".toml", ".yml", ".yaml", ".json", ".csv", ".cfg", ".ini", ".example", ""}
ENV_GIZLI = {"TRENDYOL_SATICI_ID", "TRENDYOL_API_KEY", "TRENDYOL_API_SECRET", "TRENDYOL_MAGAZA_ADI", "MUSTERI_ID_TUZ",
             "ANTHROPIC_API_KEY"}


def izlenen_dosyalar():
    cikti = subprocess.run(["git", "ls-files", "-z"], cwd=PROJE, capture_output=True, check=True).stdout
    return [p for p in cikti.decode("utf-8").split("\0") if p]


def env_degerleri():
    """Yerel .env'deki gizli değerler (yalnızca bellekte; 6 karakterden kısa değerler yanlış alarm verir, atlanır)."""
    yol = PROJE / ".env"
    if not yol.exists():
        return {}
    degerler = {}
    for satir in yol.read_text(encoding="utf-8").splitlines():
        anahtar, _, deger = satir.strip().partition("=")
        deger = deger.strip().strip("\"'")
        if anahtar.strip() in ENV_GIZLI and len(deger) >= 6 and not satir.strip().startswith("#"):
            degerler[anahtar.strip()] = deger
    return degerler


def kontrol():
    sorunlar = []
    gizli = env_degerleri()
    for yol in izlenen_dosyalar():
        for desen, neden in YASAKLI_YOL:
            if re.search(desen, yol):
                sorunlar.append((yol, f"yasaklı yol: {neden}"))
        dosya = PROJE / yol
        if not dosya.is_file():
            continue
        if dosya.stat().st_size > EN_BUYUK_MB * 1024 * 1024:
            sorunlar.append((yol, f"{EN_BUYUK_MB} MB'tan büyük"))
            continue
        if dosya.suffix.lower() not in METIN_UZANTILARI:
            continue
        try:
            metin = dosya.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for desen, neden in ICERIK:
            if desen.search(metin) and not (yol.endswith(".env.example") and neden == "dolu gizli değişken ataması"):
                sorunlar.append((yol, neden))
        for anahtar, deger in gizli.items():
            if deger in metin:
                sorunlar.append((yol, f".env'deki {anahtar} değeri bu dosyada geçiyor"))
    return sorunlar, bool(gizli)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sorunlar, env_var = kontrol()
    if sorunlar:
        print("✗ Yasaklı dosya veya gizli bilgi bulundu:")
        for yol, neden in sorunlar:
            print(f"  - {yol}: {neden}")
        print("\nDosyayı git'ten çıkarın (git rm --cached <dosya>) ve .gitignore'a ekleyin. Gizli bir anahtar push "
              "edildiyse, silmek yetmez: anahtarı yenileyin.")
        sys.exit(1)
    print("✓ Yasaklı dosya yok" + (" (.env değerleri de tarandı)" if env_var else " (.env yok; yalnızca kalıplar)"))
