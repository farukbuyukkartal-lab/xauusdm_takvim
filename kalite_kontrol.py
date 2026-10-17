#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADIM 1b: Kalite kontrol + olay/mum eslemesi  (SADE SURUM - offset yok)
=====================================================================
Girdi : CalendarExport.mq5'in FILE_COMMON altina yazdigi CSV
Cikti : Kisa metin raporu (ekrana + rapor dosyasina)

TEMIZLIK (revizyon):
  - offset_tablosu.csv mekanizmasi TAMAMEN KALDIRILDI. Gerekce: zaman_haritasi.py
    gercek veriyle olctu -> Python bar zamanlari sunucu saatiyle AYNI (fark sabit 0).
    Bu yuzden esleme dogrudan SUNUCU SAATI ile yapilir, donusum yok.
  - Birebir tekrar satirlar yuklerken ATILIR (drop_duplicates).
  - Olaylar uc sinifa ayrilir: piyasa ACIKKEN, HAFTA SONU/KAPALIYKEN, ARALIK DISI.
  - Esleme sonrasi GECIKME (dk) ayarli; varsayilan 0.
  - NFP vb. filtreleme ISIM yerine event_id ile yapilir (terminal dili Turkce).

VARSAYIMLAR (acikca):
  V1) Takvim saatleri SUNUCU saatidir (MT5 dokumani). Python barlari da ayni
      saat diliminde geldigi OLCULDU; bu yuzden donusum yok.
  V2) "Piyasa acik" tespiti: olay zamani bir mumun [t, t+gecikme] penceresine
      dusuyorsa piyasa acik sayilir. Bar araliginin disindaysa ARALIK DISI.
      Bir mumun kapanisindan sonraki ilk 5 dakika "kapali" sayilir (gun sonu).
  V3) Hafta sonu: olay zamani Cumartesi/Pazar ise HAFTA SONU/KAPALI.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import MetaTrader5 as mt5

# ===================== AYARLAR (en ustte) ==========================
CSV_ADI        = "calendar_events.csv"      # FILE_COMMON altindaki dosya adi
RAPOR_DOSYASI  = "rapor.txt"                # bu scriptin klasorunde yazilir
SEMBOL         = "XAUUSDm"
ZAMAN_DILIMI   = mt5.TIMEFRAME_M15
BASLANGIC      = datetime(2022, 7, 1)
BITIS          = None                       # None = bugun (yerel saat)
MT5_YOLU       = None
MT5_LOGIN      = None
MT5_SIFRE      = None
MT5_SUNUCU     = None
ONEM_ESIGI     = None                       # None = TUM onem seviyeleri
PIYASA_ACIK_ESIK_DK = 90                    # son bar bundan yeniyse piyasa acik sayilir

#--- Esleme: olay zamanindan SONRA acilan ilk mum + bu kadar gecikme
ESLEME_GECIKME_DK = 0                       # varsayilan 0 (olay anindan sonraki ilk mum)

#--- NFP vb. filtreleme ARTIK ISIMLE DEGIL event_id ILE yapilir.
#    Terminal dili Turkce oldugu icin isim eslesmesi kirilgan (olculdu).
#    event_id'leri takvim CSV'sinden ogrenin: ornek satiri filtreleyip
#    'event_id' kolonuna bakin (isim yalnizca yorum icin yazilmistir).
FILTRE_EVENT_IDLERI: tuple[str, ...] = ()   # ornek: ("999010001",)  -- bos = filtre yok
FILTRE_ULKE_KODU = None                     # ornek: "US"  -- None = filtre yok
# ===================================================================


# ------------------------------------------------------------------
# Yardimci: FILE_COMMON yolu
#  ONEMLI (olculdu): mt5.COMMON_DATA_PATH ve terminal_info().common_data_path
#  bu surumde YOK. Dogru yol %APPDATA%\MetaQuotes\Terminal\Common\Files;
#  terminal kokunun altinda DEGIL. Adaylar sirayla denenir.
# ------------------------------------------------------------------
def ortak_klasor() -> str:
    adaylar: list[str] = []
    env = os.environ.get("TERMINAL_COMMON_DATA_PATH")
    if env:
        adaylar.append(os.path.join(env, "Files"))
    appdata = os.environ.get("APPDATA")
    if appdata:
        adaylar.append(os.path.join(appdata, "MetaQuotes", "Terminal", "Common", "Files"))
    bilgi = mt5.terminal_info()
    if bilgi is not None:
        terminal_kok = os.path.dirname(os.path.dirname(bilgi.data_path))
        adaylar.append(os.path.join(terminal_kok, "Common", "Files"))
    else:
        print(f"[uyari] terminal_info() alinamadi: {mt5.last_error()}")

    for yol in adaylar:
        if os.path.isdir(yol):
            print(f"[yol] ortak klasor: {yol}")
            return yol
    raise RuntimeError(
        "Ortak (Common) Files klasoru bulunamadi. Denenen yollar:\n  "
        + "\n  ".join(adaylar)
    )


# ------------------------------------------------------------------
# Yardimci: CSV okuma (utf-8-sig -> utf-8 -> cp1254 -> latin-1)
#  cp1254: MQL5 FILE_ANSI + Turkce Windows (ulke/olay adlari Turkce).
# ------------------------------------------------------------------
def csv_oku(yol: str) -> pd.DataFrame:
    for kodlama in ("utf-8-sig", "utf-8", "cp1254", "latin-1"):
        try:
            df = pd.read_csv(yol, encoding=kodlama)
            print(f"[okuma] {yol} ({kodlama}) satir={len(df)}")
            return df
        except UnicodeDecodeError:
            continue
    raise RuntimeError("CSV hicbir kodlamayla okunamadi.")


# ------------------------------------------------------------------
# Yardimci: birebir tekrar satirlari at (yuklerken)
# ------------------------------------------------------------------
def tekrarlari_at(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """
    Birebir ayni satirlari atar. Karsilastirma ANAHTARI: tum ortak kolonlar.
    (Onceki surumde yalnizca olay_adi+zaman+ulke kullaniliyordu ve event_id ile
    ayni olay tekrar yazilirsa ayirt edilemiyordu.)
    """
    onceki = len(df)
    df = df.drop_duplicates(keep="first").reset_index(drop=True)
    return df, onceki - len(df)


# ------------------------------------------------------------------
# 1) Bosluk / tekrar / aylik sayim raporu
# ------------------------------------------------------------------
def kalite_kontrol(df: pd.DataFrame) -> list[str]:
    satirlar: list[str] = []
    beklenen = ["olay_zamani_sunucu", "ulke", "ulke_kodu", "para_birimi", "olay_adi",
                "event_id", "onem", "actual", "forecast", "previous"]
    eksik = [k for k in beklenen if k not in df.columns]
    if eksik:
        satirlar.append(f"UYARI: eksik kolonlar -> {eksik} "
                        "(CalendarExport.mq5'i yeniden derleyip calistirdiniz mi?)")
    satirlar.append(f"Toplam satir (tekrarlar atildiktan sonra): {len(df)}")

    if "olay_zamani_sunucu" in df.columns:
        zaman = pd.to_datetime(df["olay_zamani_sunucu"], errors="coerce")
        satirlar.append(f"Zamani bos/gecersiz satir: {int(zaman.isna().sum())} "
                        "(dosya sonu NOT satiri olabilir)")
        df = df.assign(_zaman=zaman).dropna(subset=["_zaman"])

    for kolon in ("ulke", "ulke_kodu", "para_birimi", "olay_adi", "onem", "event_id"):
        if kolon in df.columns:
            n = int(df[kolon].isna().sum() + (df[kolon].astype(str).str.strip() == "").sum())
            satirlar.append(f"Bos '{kolon}': {n}")
    for kolon in ("actual", "forecast", "previous"):
        if kolon in df.columns:
            satirlar.append(f"Bos '{kolon}': {int(df[kolon].isna().sum())}")

    if "onem" in df.columns:
        satirlar.append("Onem dagilimi: "
                        + ", ".join(f"{k}={v}" for k, v in df["onem"].value_counts().items()))

    if "_zaman" in df.columns and len(df):
        aylik = df["_zaman"].dt.to_period("M").value_counts().sort_index()
        satirlar.append(f"Aylik olay sayisi: {len(aylik)} ay, ort={len(df)/len(aylik):.1f}/ay; "
                        f"ilk={aylik.index[0]}:{aylik.iloc[0]}, son={aylik.index[-1]}:{aylik.iloc[-1]}")
    return satirlar


# ------------------------------------------------------------------
# 2) MT5 baglantisi ve mum cekme (tek atis -> olmazsa aylik pencereler)
# ------------------------------------------------------------------
def mt5_baglan() -> None:
    kwargs = {}
    if MT5_YOLU:
        kwargs["path"] = MT5_YOLU
    if MT5_LOGIN:
        kwargs.update(login=int(MT5_LOGIN), password=MT5_SIFRE, server=MT5_SUNUCU)
    if not mt5.initialize(**kwargs):
        raise RuntimeError(f"mt5.initialize() basarisiz: {mt5.last_error()}")


def mumlari_cek() -> pd.DataFrame:
    """
    2022-07-01'den bugune M15 mumlari.
    ONEMLI (olculdu): tek atis 3+ yillik copy_rates_range (-2, 'Terminal: Invalid
    params') dondurur; bu yuzden aylik pencerelere bolunur.
    """
    if not mt5.symbol_select(SEMBOL, True):
        raise RuntimeError(f"{SEMBOL} Market Watch'a eklenemedi: {mt5.last_error()}")
    bilgi = mt5.symbol_info(SEMBOL)
    if bilgi is None:
        raise RuntimeError(f"symbol_info({SEMBOL}) alinamadi: {mt5.last_error()}")

    bas = BASLANGIC
    bit = BITIS if BITIS is not None else datetime.now()
    rates = mt5.copy_rates_range(SEMBOL, ZAMAN_DILIMI, bas, bit)
    if rates is not None and len(rates) > 0:
        df = pd.DataFrame(rates)
    else:
        print(f"[uyari] tek atis copy_rates_range basarisiz ({mt5.last_error()}); "
              "aylik pencerelere bolunerek cekiliyor.")
        parcalar = []
        y, m = bas.year, bas.month
        while (y, m) <= (bit.year, bit.month):
            r = mt5.copy_rates_range(SEMBOL, ZAMAN_DILIMI, datetime(y, m, 1),
                                     datetime(y + (m // 12), (m % 12) + 1, 1))
            if r is not None and len(r):
                parcalar.append(pd.DataFrame(r))
            m += 1
            if m > 12:
                m, y = 1, y + 1
        if not parcalar:
            raise RuntimeError(f"Hicbir pencereden mum alinamadi. Son hata: {mt5.last_error()}")
        df = pd.concat(parcalar, ignore_index=True)
        df = df.drop_duplicates(subset=["time"]).sort_values("time").reset_index(drop=True)

    df["bar_zamani"] = pd.to_datetime(df["time"], unit="s")
    print(f"[MT5] {len(df)} mum: {df['bar_zamani'].iloc[0]} -> {df['bar_zamani'].iloc[-1]}")
    return df


# ------------------------------------------------------------------
# 3) Bar zaman dilimi olcumu (varsayim degil)
# ------------------------------------------------------------------
def bar_dilimi_olc(mumlar: pd.DataFrame) -> list[str]:
    satirlar: list[str] = []
    if mumlar.empty:
        return ["UYARI: mum verisi yok."]
    son_bar = mumlar["bar_zamani"].iloc[-1].to_pydatetime()
    simdi_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    fark_saat = (simdi_utc - son_bar).total_seconds() / 3600.0
    satirlar.append(f"Son M15 bar (ham): {son_bar:%Y-%m-%d %H:%M} | simdi (UTC): "
                    f"{simdi_utc:%Y-%m-%d %H:%M} | fark {fark_saat:+.2f} saat")
    if abs(fark_saat) <= PIYASA_ACIK_ESIK_DK / 60.0:
        satirlar.append(f"SONUC: bar zamanlari sunucu saatinde gorunuyor: {round(fark_saat):+d} saat")
    else:
        satirlar.append(f"SONUC: piyasa KAPALI gorunuyor (son bar {fark_saat:.1f} saat geride); "
                        "olcum ATLANDI. Hafta ici tekrar calistirin.")
    return satirlar


# ------------------------------------------------------------------
# 4) Olaylari siniflandir ve mumlara esle
# ------------------------------------------------------------------
def olaylari_esle(df: pd.DataFrame, mumlar: pd.DataFrame,
                  gecikme_dk: int = ESLEME_GECIKME_DK) -> tuple[pd.DataFrame, list[str]]:
    """
    Olayi, olay zamanindan SONRA ACILAN ILK MUMA atar (+ gecikme_dk).
    Olay mumunun icine esleme YAPILMAZ -> gelecek bilgisi sizintisi yok.

    Siniflar:
      ACIK      : olay zamani bar araliginin icinde (piyasa acik varsayimi)
      KAPALI    : olay zamani hafta sonu VEYA bar araligindaki bir mumun
                  kapanisindan sonraki boslukta (gun sonu/hafta sonu kapanisi)
      ARALIK_DISI: olay zamani bar araliginin tamamen disinda
    """
    satirlar: list[str] = []
    if "olay_zamani_sunucu" not in df.columns or mumlar.empty:
        return pd.DataFrame(), ["UYARI: esleme icin veri yetersiz."]

    olay = df.copy()
    olay["_zaman"] = pd.to_datetime(olay["olay_zamani_sunucu"], errors="coerce")
    olay = olay.dropna(subset=["_zaman"]).sort_values("_zaman").reset_index(drop=True)
    if ONEM_ESIGI is not None and "onem" in olay.columns:
        olay = olay[olay["onem"].isin(ONEM_ESIGI)].reset_index(drop=True)
    if olay.empty:
        return pd.DataFrame(), ["UYARI: eslenecek olay yok."]

    #--- event_id ile filtreleme (isimle DEGIL)
    if FILTRE_EVENT_IDLERI and "event_id" in olay.columns:
        onceki = len(olay)
        olay = olay[olay["event_id"].astype(str).isin([str(x) for x in FILTRE_EVENT_IDLERI])]
        satirlar.append(f"event_id filtresi {list(FILTRE_EVENT_IDLERI)}: "
                        f"{onceki} -> {len(olay)} olay")
    if FILTRE_ULKE_KODU and "ulke_kodu" in olay.columns:
        onceki = len(olay)
        olay = olay[olay["ulke_kodu"].astype(str).str.upper() == FILTRE_ULKE_KODU.upper()]
        satirlar.append(f"ulke_kodu filtresi '{FILTRE_ULKE_KODU}': {onceki} -> {len(olay)} olay")
    olay = olay.reset_index(drop=True)
    if olay.empty:
        return pd.DataFrame(), satirlar + ["UYARI: filtrelerden sonra olay kalmadi."]

    bar_zaman = mumlar["bar_zamani"].to_numpy()
    bar_bitis = mumlar["bar_zamani"].shift(-1)   # sonraki mumun acilisi = bu mumun bitisi
    olay_zaman = olay["_zaman"].to_numpy()

    #--- 5) Olaydan SONRA acilan ilk mum (side="left")
    idx = pd.Series(bar_zaman).searchsorted(pd.Series(olay_zaman), side="left")
    aralik_ici = (idx < len(bar_zaman)) & (olay_zaman >= bar_zaman[0])

    #--- 6) Gecikme uygula: hedef mumu gecikme kadar ileri kaydir
    if gecikme_dk > 0:
        adim = max(1, int(round(gecikme_dk / 15.0)))   # M15 icin mum adimi
        idx_hedef = np.where(aralik_ici, idx + adim, idx)
        aralik_ici = aralik_ici & (idx_hedef < len(bar_zaman))
        idx_hedef = np.clip(idx_hedef, 0, len(bar_zaman) - 1)
    else:
        idx_hedef = np.clip(idx, 0, len(bar_zaman) - 1)

    #--- 7) Siniflandirma
    hafta_sonu = pd.to_datetime(olay["_zaman"]).dt.weekday >= 5
    sinif = np.where(~aralik_ici, "ARALIK_DISI", np.where(hafta_sonu, "KAPALI", "ACIK"))

    olay["_idx"] = idx_hedef
    olay["hedef_bar"] = bar_zaman[idx_hedef]
    olay["gecikme_dk"] = (pd.to_datetime(olay["hedef_bar"]) - olay["_zaman"]).dt.total_seconds() / 60.0
    olay["sinif"] = sinif

    #--- 8) Rapor
    satirlar.append(f"Esleme gecikmesi ayari: {gecikme_dk} dk")
    for etiket, maske in (
        ("ACIK (piyasa acik varsayimi)", olay["sinif"] == "ACIK"),
        ("KAPALI (hafta sonu/gun sonu)", olay["sinif"] == "KAPALI"),
        ("ARALIK_DISI", olay["sinif"] == "ARALIK_DISI"),
    ):
        satirlar.append(f"  {etiket}: {int(maske.sum())} olay")

    eslesen = olay[olay["sinif"] != "ARALIK_DISI"]
    if len(eslesen):
        geriye = int((eslesen["hedef_bar"] < eslesen["_zaman"]).sum())
        satirlar.append(f"Kontrol: hedef bar olaydan ONCE olan satir = {geriye} (0 olmali)")
        satirlar.append(f"Kontrol: olay->bar gecikmesi (dk) ort={eslesen['gecikme_dk'].mean():.1f}, "
                        f"max={eslesen['gecikme_dk'].max():.1f}")
    satirlar.append(f"Bar araligi: {bar_zaman[0]} -> {bar_zaman[-1]}")

    dakika = pd.Series(bar_zaman).dt.minute.unique()
    satirlar.append("Kontrol: tum mum acilislari 15 dk katinda."
                    if not (set(dakika) - {0, 15, 30, 45})
                    else f"UYARI: beklenmeyen dakikalar: {sorted(set(dakika))}")
    return olay, satirlar


# ------------------------------------------------------------------
# 5) Secilen olaylarin saat dagilimi (event_id filtresi ile)
# ------------------------------------------------------------------
def saat_dagilimi(olay: pd.DataFrame) -> list[str]:
    satirlar: list[str] = []
    if olay.empty:
        return ["UYARI: dagilim icin olay yok."]
    saat = pd.to_datetime(olay["_zaman"]).dt.hour
    dagilim = saat.value_counts().sort_index()
    satirlar.append("Saat dagilimi (sunucu saati, saat: adet): "
                    + ", ".join(f"{int(k):02d}->{int(v)}" for k, v in dagilim.items()))
    satirlar.append(f"Benzersiz saat sayisi: {len(dagilim)}")
    if len(dagilim) > 1:
        ay = pd.to_datetime(olay["_zaman"]).dt.to_period("M")
        aylik = olay.assign(_ay=ay, _saat=saat).groupby("_ay")["_saat"].apply(
            lambda s: sorted(set(s)))
        gecis = aylik[aylik.apply(len) > 1]
        if len(gecis):
            satirlar.append("Ayni ay icinde birden fazla saat: "
                            + ", ".join(str(a) for a in gecis.index))
        satirlar.append("NOT: birden fazla saat -> yaz/kis (DST) gecisi.")
    else:
        satirlar.append("NOT: tek saat -> sunucu saati sabit gorunuyor.")
    if "sinif" in olay.columns:
        satirlar.append("Sinif dagilimi: "
                        + ", ".join(f"{k}={v}" for k, v in olay["sinif"].value_counts().items()))
    return satirlar


# ------------------------------------------------------------------
# Ana akis
# ------------------------------------------------------------------
def main() -> None:
    mt5_baglan()
    try:
        csv_yolu = os.path.join(ortak_klasor(), CSV_ADI)
        if not os.path.exists(csv_yolu):
            raise FileNotFoundError(f"CSV bulunamadi: {csv_yolu}\n"
                                    "Once MT5'te CalendarExport.mq5'i calistirin.")

        ham = csv_oku(csv_yolu)
        df, atilan = tekrarlari_at(ham)

        rapor: list[str] = []
        rapor.append("=== 0) TEKRAR TEMIZLIGI ===")
        rapor.append(f"Birebir tekrar satir atildi: {atilan} "
                     f"({len(ham)} -> {len(df)})")

        rapor.append("")
        rapor.append("=== 1) KALITE KONTROL ===")
        rapor += kalite_kontrol(df)

        rapor.append("")
        rapor.append("=== 2) MT5 VERISI ===")
        mumlar = mumlari_cek()
        rapor.append(f"Cekilen mum: {len(mumlar)} adet {SEMBOL} M15")

        rapor.append("")
        rapor.append("=== 3) BAR ZAMAN DILIMI OLCUMU ===")
        rapor += bar_dilimi_olc(mumlar)

        rapor.append("")
        rapor.append("=== 4) ESLEME (sunucu saati, offset YOK, sonra acilan ilk mum) ===")
        olay, satir4 = olaylari_esle(df, mumlar)
        rapor += satir4

        rapor.append("")
        rapor.append("=== 5) SAAT DAGILIMI (event_id filtresi ile) ===")
        rapor += saat_dagilimi(olay)

        metin = "\n".join(rapor)
        print("\n" + metin)
        with open(RAPOR_DOSYASI, "w", encoding="utf-8") as f:
            f.write(metin + "\n")
        print(f"\n[rapor] {os.path.abspath(RAPOR_DOSYASI)} yazildi.")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
