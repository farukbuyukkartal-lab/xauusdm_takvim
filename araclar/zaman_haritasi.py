#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EK ADIM: Zaman haritasi (MQL5 barlari vs Python barlari)
========================================================
Girdi : bars_mql5.csv (BarExport.mq5'in FILE_COMMON'a yazdigi dosya)
Cikti : rapor (ekran + metin) ve offset_tablosu.csv

Ne yapar:
  1) bars_mql5.csv'yi okur (MQL5 tarafinin bar zamanlari, SUNUCU saati).
  2) Ayni aralikta Python tarafindan M15 barlarini ceker.
  3) Satirlari SIRAYA gore esler; satir sayilari esit degilse ACIKCA raporlar.
  4) Eslesmeyi OHLC + tick_volume esitlik oraniyla dogrular.
  5) Her bar icin fark = python_epoch - mql5_epoch hesaplar; saat bazinda dagilim,
     aylik min/max, farkin degistigi tarihler (yaz/kis gecisi).
  6) offset_tablosu.csv uretir: tarih, fark_saat.
  7) Sonucu acikca yazar: AYNI / X saat farkli (DST ile degisiyor mu: evet/hayir).

Piyasa acik olmasi gerekmez: fark, ayni donemdeki barlarin ZAMAN DAMGALARI
karsilastirilarak olculur, "simdi"ye bakilmaz.

VARSAYIMLAR (acikca):
  A1) MT5 Python'da bar zamanlari "terminal/sunucu saati" olarak gelir (Python
      tarafinda UTC'ye cevrilmez). Bu script bunu VARSAYMAZ, OLCER ve raporlar.
  A2) bars_mql5.csv'deki zaman_sunucu_epoch = MQL5 sunucu saatinin epoch karsiligi.
  A3) Esleme SIRAYA goredir (senin istedigin gibi); once satir sayilari
      karsilastirilir, sonra icerik esitligi orani ile dogrulanir.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import MetaTrader5 as mt5

# ===================== AYARLAR (en ustte) ==========================
MQL5_CSV       = "bars_mql5.csv"       # FILE_COMMON altinda (BarExport.mq5 yazar)
OFFSET_CSV     = "offset_tablosu.csv"  # bu scriptin klasorune yazilir
SEMBOL         = "XAUUSDm"
ZAMAN_DILIMI   = mt5.TIMEFRAME_M15
BASLANGIC      = datetime(2022, 7, 1)  # MQL5 ile AYNI pencere (sunucu saati)
BITIS          = None                  # None = bugun
MT5_YOLU       = None                  # ornek: r"C:\\Program Files\\MetaTrader 5\\terminal64.exe"
MT5_LOGIN      = None
MT5_SIFRE      = None
MT5_SUNUCU     = None
AYLIK_TOLERANS_SAAT = 0.01             # aylik min/max karsilastirmasinda kayan nokta toleransi
# ===================================================================


# ------------------------------------------------------------------
# Yardimci: FILE_COMMON yolu (Windows: ...\\MetaQuotes\\Terminal\\Common\\Files)
#
# ONEMLI (olculdu, 17.10.2026): MT5 Python'da COMMON_DATA_PATH sabiti YOK,
# terminal_info()'da common_data_path alani da YOK. Ayrica ortak klasor
# terminal kokunun (data_path'in iki seviye ustu) altinda DEGIL;
# %APPDATA%\\MetaQuotes\\Terminal\\Common\\Files altindadir. Eski surumdeki
# tek-aday varsayimi bu yuzden dosyayi bulamiyordu.
# Adaylar sirayla denenir, ilk var olan kullanilir.
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
        + "\nMT5'te bir script calistirip FILE_COMMON dosyasi olusturun ya da "
        "TERMINAL_COMMON_DATA_PATH degiskenini tanimlayin."
    )


def csv_oku(yol: str) -> pd.DataFrame:
    # cp1254: MQL5 FILE_ANSI ile Turkce Windows'ta uretilen dosyalar (ulke/olay
    # adlari Turkce karakter icerir). Once UTF aileleri, sonra cp1254, en son latin-1.
    for kodlama in ("utf-8-sig", "utf-8", "cp1254", "latin-1"):
        try:
            df = pd.read_csv(yol, encoding=kodlama)
            print(f"[okuma] {yol} ({kodlama}) satir={len(df)}")
            return df
        except UnicodeDecodeError:
            continue
    raise RuntimeError("CSV hicbir kodlamayla okunamadi.")


# ------------------------------------------------------------------
# 1) Python barlarini cek (tek pencere denenir; olmazsa aylik pencerelere boler)
# ------------------------------------------------------------------
def mt5_baglan() -> None:
    kwargs = {}
    if MT5_YOLU:
        kwargs["path"] = MT5_YOLU
    if MT5_LOGIN:
        kwargs.update(login=int(MT5_LOGIN), password=MT5_SIFRE, server=MT5_SUNUCU)
    if not mt5.initialize(**kwargs):
        raise RuntimeError(f"mt5.initialize() basarisiz: {mt5.last_error()}")


def python_barlari_cek() -> tuple[pd.DataFrame, list[str]]:
    """
    Tek atis copy_rates_range dener; bos/None donerse aylik pencerelere boler.
    GEREKCE (olculdu): bu kurulumda 3+ yillik tek atis istek
    (-2, 'Terminal: Invalid params') dondururken aylik pencereler sorunsuz calisti.
    """
    notlar: list[str] = []
    if not mt5.symbol_select(SEMBOL, True):
        raise RuntimeError(f"{SEMBOL} Market Watch'a eklenemedi: {mt5.last_error()}")
    bilgi = mt5.symbol_info(SEMBOL)
    if bilgi is None:
        raise RuntimeError(f"symbol_info({SEMBOL}) alinamadi: {mt5.last_error()}")

    bas = BASLANGIC
    bit = BITIS if BITIS is not None else datetime.now()
    rates = mt5.copy_rates_range(SEMBOL, ZAMAN_DILIMI, bas, bit)
    if rates is not None and len(rates) > 0:
        notlar.append(f"Python barlari: tek atis copy_rates_range ile {len(rates)} bar.")
    else:
        notlar.append(
            f"UYARI: tek atis copy_rates_range basarisiz ({mt5.last_error()}); "
            "aylik pencerelere bolunerek cekiliyor."
        )
        parcalar = []
        y, m = bas.year, bas.month
        while (y, m) <= (bit.year, bit.month):
            p_bas = datetime(y, m, 1)
            p_bit = datetime(y + (m // 12), (m % 12) + 1, 1)
            r = mt5.copy_rates_range(SEMBOL, ZAMAN_DILIMI, p_bas, p_bit)
            if r is not None and len(r):
                parcalar.append(pd.DataFrame(r))
            m += 1
            if m > 12:
                m, y = 1, y + 1
        if not parcalar:
            raise RuntimeError("Hicbir pencereden bar alinamadi.")
        rates_df = pd.concat(parcalar, ignore_index=True)
        rates_df = rates_df.drop_duplicates(subset=["time"]).sort_values("time").reset_index(drop=True)
        notlar.append(f"Python barlari: aylik pencerelerle {len(rates_df)} bar.")
        df = rates_df
        df["py_zaman"] = pd.to_datetime(df["time"], unit="s")
        return df[["time", "py_zaman", "open", "high", "low", "close", "tick_volume"]], notlar

    df = pd.DataFrame(rates)
    df["py_zaman"] = pd.to_datetime(df["time"], unit="s")
    return df[["time", "py_zaman", "open", "high", "low", "close", "tick_volume"]], notlar


# ------------------------------------------------------------------
# 2) MQL5 CSV'sini hazirla (NOT satirini at)
# ------------------------------------------------------------------
def mql5_barlari(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["mql5_epoch"] = pd.to_numeric(df["zaman_sunucu_epoch"], errors="coerce")
    df["mql5_zaman"] = pd.to_datetime(df["zaman_sunucu"], errors="coerce")
    gecerli = df["mql5_epoch"].notna() & df["mql5_zaman"].notna()
    atilan = int((~gecerli).sum())
    df = df[gecerli].reset_index(drop=True)
    if atilan:
        print(f"[not] {atilan} satir (NOT satiri / bos zaman) disarida birakildi.")
    for k in ("open", "high", "low", "close", "tick_volume"):
        df[k] = pd.to_numeric(df[k], errors="coerce")
    return df


# ------------------------------------------------------------------
# 3) Siraya gore esleme + OHLC/tick_volume dogrulamasi
# ------------------------------------------------------------------
def siraya_gore_esle(m5: pd.DataFrame, py: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    satirlar: list[str] = []
    satirlar.append(f"MQL5 bar sayisi: {len(m5)}  (ilk {m5['mql5_zaman'].iloc[0]}, "
                    f"son {m5['mql5_zaman'].iloc[-1]})" if len(m5) else "MQL5 bar sayisi: 0")
    satirlar.append(f"Python bar sayisi: {len(py)} (ilk {py['py_zaman'].iloc[0]}, "
                    f"son {py['py_zaman'].iloc[-1]})" if len(py) else "Python bar sayisi: 0")

    if len(m5) != len(py):
        fark = len(py) - len(m5)
        satirlar.append(
            f"UYARI: SATIR SAYILARI ESIT DEGIL (fark {fark:+d}). "
            "Siraya gore esleme yine yapilir ama sonuclar guvenilmez; "
            "iki tarafin ayni baslangic/bitis penceresini istedigi ve veri derinliginin "
            "ayni oldugu kontrol edilmeli."
        )
    else:
        satirlar.append("Kontrol: satir sayilari ESIT.")

    n = min(len(m5), len(py))
    if n == 0:
        return pd.DataFrame(), satirlar + ["UYARI: eslenecek bar yok."]

    es = pd.DataFrame({
        "mql5_epoch": m5["mql5_epoch"].to_numpy()[:n],
        "mql5_zaman": m5["mql5_zaman"].to_numpy()[:n],
        "py_epoch":   py["time"].to_numpy()[:n],
        "py_zaman":   py["py_zaman"].to_numpy()[:n],
    })
    for k in ("open", "high", "low", "close", "tick_volume"):
        es[f"m_{k}"] = pd.to_numeric(m5[k], errors="coerce").to_numpy()[:n]
        es[f"p_{k}"] = pd.to_numeric(py[k], errors="coerce").to_numpy()[:n]

    # OHLC + tick_volume esitlik orani
    esit = np.ones(n, dtype=bool)
    for k in ("open", "high", "low", "close", "tick_volume"):
        esit &= (es[f"m_{k}"].to_numpy() == es[f"p_{k}"].to_numpy())
    oran = float(esit.sum()) / n * 100.0
    satirlar.append(f"OHLC+tick_volume BIREBIR esit satir: {int(esit.sum())} / {n} = {oran:.2f}%")

    # Fiyatlarda kayan nokta farki da olabilir: yakinlik kontrolu ikinci olcu
    yakin = np.ones(n, dtype=bool)
    for k in ("open", "high", "low", "close"):
        yakin &= (es[f"m_{k}"] - es[f"p_{k}"]).abs().to_numpy() <= 1e-6
    satirlar.append(f"OHLC yaklasik esit (<=1e-6) satir: {int(yakin.sum())} / {n} "
                    f"= {yakin.sum()/n*100.0:.2f}%")
    if oran < 100.0:
        farkli = int((~esit).sum())
        satirlar.append(f"UYARI: {farkli} satirda veri birebir ayni degil. "
                        "Siraya gore esleme kaymis olabilir (eksik/fazla bar).")
    return es, satirlar


# ------------------------------------------------------------------
# 4) Fark dagilimi + aylik min/max + gecis tarihleri
# ------------------------------------------------------------------
def fark_analizi(es: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    satirlar: list[str] = []
    if es.empty:
        return es, ["UYARI: fark analizi icin veri yok."]

    es = es.copy()
    es["fark_saat"] = (es["py_epoch"] - es["mql5_epoch"]) / 3600.0
    es["ay"] = pd.to_datetime(es["mql5_zaman"]).dt.to_period("M")

    # Saat bazinda dagilim
    yuvarlak = es["fark_saat"].round()   # tam saat beklenir
    dagilim = yuvarlak.value_counts().sort_index()
    satirlar.append(f"Fark dagilimi (yuvarlak saat: adet): "
                    + ", ".join(f"{int(k):+d}->{int(v)}" for k, v in dagilim.items()))
    benzersiz = sorted(set(es["fark_saat"].round(6)))
    satirlar.append(f"Benzersiz (yuvarlanmamis) fark degerleri: {len(benzersiz)} adet; "
                    f"ilk 5: {benzersiz[:5]}")
    if len(benzersiz) > 1:
        satirlar.append("NOT: birden fazla fark degeri -> yaz/kis (DST) veya tek seferlik kayma.")

    # Aylik min/max
    aylik = es.groupby("ay")["fark_saat"].agg(["min", "max", "count"])
    satirlar.append("Aylik fark (saat) - ilk 6 / son 6 ay:")
    for ay, r in list(aylik.iterrows())[:6]:
        satirlar.append(f"  {ay}: min={r['min']:+.3f} max={r['max']:+.3f} bar={int(r['count'])}")
    if len(aylik) > 12:
        satirlar.append("  ...")
    for ay, r in list(aylik.iterrows())[-6:]:
        satirlar.append(f"  {ay}: min={r['min']:+.3f} max={r['max']:+.3f} bar={int(r['count'])}")

    # Farkin degistigi tarihler (yaz/kis gecisi)
    es = es.sort_values("mql5_zaman").reset_index(drop=True)
    degisim = es["fark_saat"].diff().abs() > AYLIK_TOLERANS_SAAT
    gecis = es.loc[degisim, ["mql5_zaman", "fark_saat"]]
    satirlar.append(f"Farkin degistigi tarih sayisi: {len(gecis)}")
    for _, r in gecis.iterrows():
        satirlar.append(f"  GECIS: {r['mql5_zaman']} -> yeni fark {r['fark_saat']:+.2f} saat")
    return es, satirlar


# ------------------------------------------------------------------
# 5) offset_tablosu.csv uret
# ------------------------------------------------------------------
def offset_tablosu_yaz(es: pd.DataFrame, yol: str) -> list[str]:
    if es.empty:
        return ["UYARI: offset_tablosu.csv yazilmadi (veri yok)."]
    tablo = es[["mql5_zaman", "fark_saat"]].rename(
        columns={"mql5_zaman": "tarih", "fark_saat": "fark_saat"}
    )
    tablo.to_csv(yol, index=False, encoding="utf-8")
    return [f"offset_tablosu.csv yazildi: {yol} ({len(tablo)} satir, kolonlar: tarih, fark_saat)"]


# ------------------------------------------------------------------
# Ana akis
# ------------------------------------------------------------------
def main() -> None:
    mt5_baglan()
    sonuc: list[str] = []
    try:
        common = ortak_klasor()
        csv_yolu = os.path.join(common, MQL5_CSV)
        print(f"[yol] MQL5 CSV: {csv_yolu}")
        if not os.path.exists(csv_yolu):
            raise FileNotFoundError(
                f"MQL5 CSV bulunamadi: {csv_yolu}\nOnce MT5'te BarExport.mq5 scriptini calistirin."
            )

        rapor: list[str] = []
        rapor.append("=== 1) VERI ===")
        m5 = mql5_barlari(csv_oku(csv_yolu))
        py, notlar = python_barlari_cek()
        rapor += notlar

        rapor.append("")
        rapor.append("=== 2) SIRAYA GORE ESLEME VE DOGRULAMA ===")
        es, satir2 = siraya_gore_esle(m5, py)
        rapor += satir2

        rapor.append("")
        rapor.append("=== 3) FARK ANALIZI ===")
        es, satir3 = fark_analizi(es)
        rapor += satir3

        rapor.append("")
        rapor.append("=== 4) OFFSET TABLOSU ===")
        rapor += offset_tablosu_yaz(es, OFFSET_CSV)

        # Sonuc cumlesi
        rapor.append("")
        rapor.append("=== 5) SONUC ===")
        if es.empty:
            rapor.append("SONUC: olcum yapilamadi.")
        else:
            degerler = sorted(set(es["fark_saat"].round(6)))
            if len(degerler) == 1 and abs(degerler[0]) < 1e-9:
                rapor.append("SONUC: Python barlari sunucu saatiyle AYNI.")
            else:
                ana = max(set(es["fark_saat"].round()), key=list(es["fark_saat"].round()).count)
                dst = "evet" if len(degerler) > 1 else "hayir"
                rapor.append(f"SONUC: Python barlari sunucudan {ana:+d} saat farkli "
                             f"(DST ile degisiyor mu: {dst})")
                if dst == "evet":
                    rapor.append("       (fark degerleri: "
                                 + ", ".join(f"{d:+.2f}" for d in degerler[:10])
                                 + (" ..." if len(degerler) > 10 else "") + ")")

        metin = "\n".join(rapor)
        print("\n" + metin)
        with open("zaman_haritasi_rapor.txt", "w", encoding="utf-8") as f:
            f.write(metin + "\n")
        print("\n[rapor] zaman_haritasi_rapor.txt yazildi.")
        sonuc = rapor
    finally:
        mt5.shutdown()
    return sonuc


if __name__ == "__main__":
    main()
