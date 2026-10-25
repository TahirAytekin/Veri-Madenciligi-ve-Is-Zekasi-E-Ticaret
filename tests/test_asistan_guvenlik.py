"""Asistan güvenlik testleri (F4-06): SQL ile yazma ve dosya erişimi denemeleri, müşteri metninin veri olarak
işaretlenmesi.

Modelin gömülü talimata uymadığı, sohbet değerlendirmesinde (F4-05) API ile ayrıca ölçülür.
"""
import json

import pytest

from analiz import metrikler as m
from asistan import araclar as a


def _sql(sorgu):
    return json.loads(a.calistir("sql_sorgula", {"sorgu": sorgu}, "sahte"))


@pytest.mark.parametrize("sorgu", [
    "drop table urunler",
    "DELETE FROM urunler",
    "insert into urunler select * from urunler",
    "update urunler set stok = 0",
    "create table x as select 1",
    "select 1; drop table urunler",
    "select 1;\ndelete from urunler",
    "attach 'baska.db' as b",
    "copy urunler to 'sizinti.csv'",
    "pragma database_list",
    "set enable_external_access = true",
    "install httpfs",
    "load httpfs",
    "with x as (select 1) delete from urunler",
])
def test_yazma_ve_yonetim_engellenir(sorgu):
    r = _sql(sorgu)
    assert "hata" in r, sorgu
    assert len(m.tablolar("sahte")["urunler"]) > 0                         # tablolar yerinde


@pytest.mark.parametrize("sorgu", [
    "select * from read_csv_auto('README.md')",
    "select * from read_text('.env')",
    "select * from 'veri/sahte/urunler.csv'",
    "select * from read_parquet('https://example.com/x.parquet')",
])
def test_dosya_ve_ag_erisimi_kapali(sorgu):
    r = _sql(sorgu)
    assert "hata" in r, sorgu
    assert ".env" not in json.dumps(r.get("satirlar", []))


def test_dis_erisim_ayari_kilitli():
    r = _sql("select value from duckdb_settings() where name = 'enable_external_access'")
    assert r["satirlar"] == [["false"]]


def test_yorum_satiri_ile_gizlenen_komut_calismaz():
    r = _sql("select count(*) from urunler -- ; drop table urunler")
    assert r["satirlar"][0][0] == len(m.tablolar("sahte")["urunler"])


def test_metin_sabitindeki_kelime_engellenmez():
    assert _sql("select 'drop table' as metin")["satirlar"] == [["drop table"]]


def test_musteri_metni_veri_olarak_isaretlenir():
    r = _sql("select yorum from urun_yorumlari limit 3")
    assert r["uyari"] == a.VERI_UYARISI
    r = _sql("select soru, cevap from sorular limit 3")
    assert "uyari" in r
    assert "uyari" not in _sql("select count(*) from sorular")


def test_veri_seti_modelden_secilemez():
    # Araç şemalarında veri seti seçen bir alan yok: model sahteden gerçeğe (ya da tersi) geçemez
    for s in a.semalar():
        assert not {"veri", "veri_seti", "dosya", "yol"} & set(s["input_schema"]["properties"])
