#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FRED gunluk seri indirici
=========================
Seriler : DFII10, DGS10, DGS2, T10YIE, VIXCLS
Aralik  : AYARLAR bolumundeki BASLANGIC -> bugun
Cikti   : fred_gunluk.csv  (tarih, seri, deger, kullanilabilir_tarih)

ONEMLI - GELECEK BILGISI SIZINTISI YOK:
  "kullanilabilir_tarih" = degerin TARIHINDEN SONRAKI IS GUNU.
  Yani 2022-01-03 tarihli DFII10 degeri, ancak 2022-01-04 tarihinde
  bilinebilir kabul edilir. Birlestirmelerde bu kolon kullanilmali.

API ANAHTARI:
  Kodda TUTULMAZ. Ortam degiskeninden okunur: FRED_API_KEY
    Windows PowerShell (kalici):
      setx FRED_API_KEY "buraya_anahtar"
    Ayni oturum icin:
      $env:FRED_API_KEY="buraya_anahtar"
  Anahtar yoksa script ACIK hata verir (gizli basarisizlik yok).

BOŞ DEGERLER:
  NaN degerler OLDUGU GIBI birakilir; ileri doldurma YAPILMAZ (ayarla kapatilabilir).
"""

from __future__ import annotations

import csv
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

import pandas as pd

# ===================== AYARLAR (en ustte) ==========================
SERILER          = ["DFII10", "DGS10", "DGS2", "T10YIE", "VIXCLS"]
BASLANGIC        = "2022-01-01"        # ISO tarih (FRED observation_start)
BITIS            = None                # None = bugun
CIKTI_DOSYASI    = "fred_gunluk.csv"
API_ANAHTAR_ENV  = "FRED_API_KEY"      # anahtarin okunacagi ortam degiskeni
API_TABANI       = "https://api.stlouisfed.org/fred/series/observations"
ZAMAN_ASIMI      = 30                  # saniye
ILERI_DOLDUR     = False               # True yaparsaniz NaN'lar ileri doldurulur
BEKLEME_SN       = 1.0                 # istekler arasi nazik bekleme (FRED limiti)
# ===================================================================


# ------------------------------------------------------------------
# Yardimci: API anahtarini ortam degiskeninden al
# ------------------------------------------------------------------
def api_anahtari() -> str:
    anahtar = os.environ.get(API_ANAHTAR_ENV, "").strip()
    if not anahtar:
        raise RuntimeError(
            f"API anahtari bulunamadi: '{API_ANAHTAR_ENV}' ortam degiskeni bos.\n"
            "Windows'ta kalici tanimlamak icin:\n"
            f'  setx {API_ANAHTAR_ENV} "anahtariniz"\n'
            "sonra terminali yeniden acin. Anahtar: https://fred.stlouisfed.org/docs/api/api_key.html"
        )
    return anahtar


# ------------------------------------------------------------------
# Yardimci: FRED'den bir seriyi indir (JSON)
# ------------------------------------------------------------------
def seri_indir(seri: str, anahtar: str) -> pd.DataFrame:
    parametreler = {
        "series_id": seri,
        "api_key": anahtar,
        "file_type": "json",
        "observation_start": BASLANGIC,
    }
    if BITIS:
        parametreler["observation_end"] = BITIS
    url = API_TABANI + "?" + urllib.parse.urlencode(parametreler)

    try:
        with urllib.request.urlopen(url, timeout=ZAMAN_ASIMI) as yanit:
            govde = yanit.read().decode("utf-8")
    except urllib.error.HTTPError as hata:
        # FRED hata govdesi JSON: error_code + error_message
        ayrinti = ""
        try:
            ayrinti = hata.read().decode("utf-8", "replace")
            veri = json.loads(ayrinti)
            ayrinti = f"{veri.get('error_code')}: {veri.get('error_message')}"
        except Exception:  # noqa: BLE001
            pass
        raise RuntimeError(
            f"FRED istegi basarisiz (seri={seri}, HTTP {hata.code}). {ayrinti}\n"
            "Ipucu: 400 genelde anahtar gecersiz/eksik, 429 ise istek limiti asildi."
        ) from hata
    except urllib.error.URLError as hata:
        raise RuntimeError(f"FRED'e baglanilamadi (seri={seri}): {hata.reason}") from hata

    try:
        veri = json.loads(govde)
    except json.JSONDecodeError as hata:
        raise RuntimeError(f"FRED yaniti JSON degil (seri={seri}): {hata}") from hata

    if "observations" not in veri:
        raise RuntimeError(
            f"FRED yanitinda 'observations' yok (seri={seri}). Yanit: {govde[:300]}"
        )

    df = pd.DataFrame(veri["observations"])
    if df.empty:
        return df
    df = df[["date", "value"]].rename(columns={"date": "tarih", "value": "deger"})
    df["tarih"] = pd.to_datetime(df["tarih"], errors="coerce")
    # FRED eksik degerleri "." olarak doner -> NaN (ileri doldurma YOK)
    df["deger"] = pd.to_numeric(df["deger"].replace({".": None}), errors="coerce")
    df["seri"] = seri
    return df.dropna(subset=["tarih"])


# ------------------------------------------------------------------
# Yardimci: tarihten SONRAKI is gunu (hafta sonu atlanir, tatil bilinmez)
# ------------------------------------------------------------------
def sonraki_is_gunu(t: date) -> date:
    """
    t'den SONRAKI ilk is gunu (Cumartesi/Pazar atlanir).

    VARSAYIM (acikca): ABD piyasa tatilleri (Thanksgiving, 4 Temmuz vb.) burada
    ATLANMAZ; yalnizca hafta sonu atlanir. Tatiller hesaba katilmak istenirse
    'pandas.tseries.holiday.USFederalHolidayCalendar' ile genisletilmeli.
    """
    g = t + timedelta(days=1)
    while g.weekday() >= 5:      # 5=Cumartesi, 6=Pazar
        g += timedelta(days=1)
    return g


# ------------------------------------------------------------------
# Yardimci: ileri doldurma (varsayilan KAPALI)
# ------------------------------------------------------------------
def ileri_doldur(df: pd.DataFrame) -> pd.DataFrame:
    if not ILERI_DOLDUR:
        return df
    df = df.sort_values(["seri", "tarih"]).copy()
    df["deger"] = df.groupby("seri")["deger"].ffill()
    return df


# ------------------------------------------------------------------
# Ana akis
# ------------------------------------------------------------------
def main() -> int:
    try:
        anahtar = api_anahtari()
    except RuntimeError as hata:
        # Anahtar eksik: ACIK mesaj, yigin izi yok.
        print("[HATA] " + str(hata), file=sys.stderr)
        return 1
    print(f"[bilgi] {len(SERILER)} seri indiriliyor: {', '.join(SERILER)}")
    print(f"[bilgi] aralik: {BASLANGIC} -> {BITIS or 'bugun'} | ileri_doldur={ILERI_DOLDUR}")

    parcalar = []
    hatalar = []
    for i, seri in enumerate(SERILER):
        try:
            df = seri_indir(seri, anahtar)
        except RuntimeError as hata:
            hatalar.append(f"{seri}: {hata}")
            print(f"[HATA] {seri}: {hata}")
            continue
        if df.empty:
            hatalar.append(f"{seri}: veri donmedi (aralik/gecerli seri kontrol edin).")
            print(f"[uyari] {seri}: bos dondu.")
            continue
        df["kullanilabilir_tarih"] = df["tarih"].dt.date.map(sonraki_is_gunu)
        df["kullanilabilir_tarih"] = pd.to_datetime(df["kullanilabilir_tarih"])
        parcalar.append(df)
        print(f"[ok] {seri}: {len(df)} gozlem "
              f"({df['tarih'].min().date()} -> {df['tarih'].max().date()}), "
              f"NaN={int(df['deger'].isna().sum())}")
        if i < len(SERILER) - 1:
            import time
            time.sleep(BEKLEME_SN)

    if not parcalar:
        print("[HATA] Hicbir seri indirilemedi. Yukaridaki mesajlara bakin.")
        return 1

    tumu = pd.concat(parcalar, ignore_index=True)
    tumu = tumu.sort_values(["seri", "tarih"]).reset_index(drop=True)
    tumu = ileri_doldur(tumu)
    tumu = tumu[["tarih", "seri", "deger", "kullanilabilir_tarih"]]
    tumu.to_csv(CIKTI_DOSYASI, index=False, encoding="utf-8", quoting=csv.QUOTE_MINIMAL)

    print(f"\n[ok] {CIKTI_DOSYASI} yazildi: {len(tumu)} satir, {tumu['seri'].nunique()} seri.")
    print(f"[bilgi] toplam NaN: {int(tumu['deger'].isna().sum())} (ileri doldurma: {ILERI_DOLDUR})")
    if hatalar:
        print("\n[uyari] Eksik seriler:")
        for h in hatalar:
            print("  -", h)
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[iptal] Kullanici durdurdu.", file=sys.stderr)
        sys.exit(130)
