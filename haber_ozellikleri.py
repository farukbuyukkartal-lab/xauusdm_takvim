#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADIM 3: Haber/makro ozellikleri
================================
Her M15 bar icin bir ozellik satiri uretir. Ayarlar haber_ayar.yaml'dan okunur.

CIKTI:
  haber_ozellikleri.csv   (indeks = bar zamani, SUNUCU saati)
  ozellik_katalogu.md     (her ozelligin adi, aciklamasi, parametresi)

ZORUNLU TEST:
  Kesme testi (leakage test): rastgele 20 zaman noktasi T secilir; ozellikler
  yalnizca T'ye kadar olan veriyle yeniden hesaplanir ve T'DEN ONCEKI barlarin
  ozellikleri tam veriyle hesaplananlarla karsilastirilir. Fark olmamali.

MODEL EGITIMI YAPILMAZ. Mevcut model dosyalarina DOKUNULMAZ.

VARSAYIMLAR (acikca):
  V1) Bar zamanlari ve takvim zamanlari SUNUCU saatidir (olculdu, fark sabit 0).
  V2) Sizinti kurallari:
      - Bir barin ozellikleri YALNIZCA o bar KAPANDIKTAN SONRA bilinen veriyle
        hesaplanir. Bar [t, t+15dk) araligini kapsar; "bilgi zamani" = t+15dk.
      - Takvim olayi icin actual/forecast degerleri olay ANINDA bilinir kabul edilir
        (MT5 takvimi yayin aninda guncellenir).
      - FRED satirlari "kullanilabilir_tarih + gecikme_saat" anindan itibaren bilinir.
      - Sürpriz z-skoru yalnizca ONCEKI yayinlarla hesaplanir (expanding std).
  V3) "Son olay" = bilgi zamani itibariyle yayinlanmis en son olay; sonraki olaylar
      KULLANILMAZ (gelecek bilgisi yok). Bu yuzden kalan_dk ozelligi, veri
      penceresinin SONUNDA yalnizca sonraki olay biliniyorsa doludur.
"""

from __future__ import annotations

import os
import sys
from datetime import timedelta

import numpy as np
import pandas as pd
import yaml

# ===================== AYARLAR (en ustte) ==========================
AYAR_DOSYASI   = "haber_ayar.yaml"
VARSAYILAN_AYAR = {
    "genel": {"barlar_dosyasi": "bars_mql5.csv", "cikti_dosyasi": "haber_ozellikleri.csv",
              "katalog_dosyasi": "ozellik_katalogu.md"},
    "takvim": {"aktif": True, "dosya": "calendar_events.csv", "ulke_kodu": "US",
               "onem_esigi": "high", "event_id_filtresi": [],
               "kalan_dakika": {"aktif": True, "ad": "takvim_kalan_dk", "ust_sinir_dk": 1440},
               "gecen_dakika": {"aktif": True, "ad": "takvim_gecen_dk", "ust_sinir_dk": 1440},
               "pencere": {"aktif": True, "ad": "takvim_pencere", "once_dk": 15, "sonra_dk": 15},
               "surpriz_z": {"aktif": True, "ad": "takvim_surpriz_z", "min_gecmis": 5},
               "sonumlenme": {"aktif": True, "ad": "takvim_surpriz_z_sonumlu", "yarilanma_dk": 240},
               "piyasa_durumu": {"aktif": True, "ad_hafta_sonu": "takvim_hafta_sonu",
                                 "ad_piyasa_kapali": "takvim_piyasa_kapali",
                                 "gun_sonu_bosluk_dk": 0}},
    "fred": {"aktif": True, "dosya": "fred_gunluk.csv", "gecikme_saat": 0, "seriler": {}},
    "sizinti_testi": {"aktif": True, "nokta_sayisi": 20, "rastgele_tohum": 42, "tolerans": 1e-9},
}
ONEM_SIRA = {"none": 0, "low": 1, "moderate": 2, "high": 3}
# ===================================================================


# ------------------------------------------------------------------
# Ayarlari yukle (eksikler VARSAYILAN_AYAR'dan tamamlanir)
# ------------------------------------------------------------------
def ayar_yukle(yol: str = AYAR_DOSYASI) -> dict:
    def birlestir(temel: dict, gelen: dict) -> dict:
        sonuc = dict(temel)
        for k, v in (gelen or {}).items():
            sonuc[k] = birlestir(temel[k], v) if isinstance(temel.get(k), dict) and isinstance(v, dict) else v
        return sonuc

    if not os.path.exists(yol):
        print(f"[uyari] {yol} yok; varsayilan ayarlar kullaniliyor.")
        return VARSAYILAN_AYAR
    with open(yol, encoding="utf-8") as f:
        return birlestir(VARSAYILAN_AYAR, yaml.safe_load(f) or {})


# ------------------------------------------------------------------
# Dosya okuma yardimcilari (kodlama: utf-8-sig -> utf-8 -> cp1254 -> latin-1)
# ------------------------------------------------------------------
def csv_oku(yol: str) -> pd.DataFrame:
    for kodlama in ("utf-8-sig", "utf-8", "cp1254", "latin-1"):
        try:
            return pd.read_csv(yol, encoding=kodlama)
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"CSV hicbir kodlamayla okunamadi: {yol}")


def ortak_klasor() -> str:
    """FILE_COMMON yolu (olculdu: %APPDATA%\\MetaQuotes\\Terminal\\Common\\Files)."""
    adaylar = []
    env = os.environ.get("TERMINAL_COMMON_DATA_PATH")
    if env:
        adaylar.append(os.path.join(env, "Files"))
    appdata = os.environ.get("APPDATA")
    if appdata:
        adaylar.append(os.path.join(appdata, "MetaQuotes", "Terminal", "Common", "Files"))
    for yol in adaylar:
        if os.path.isdir(yol):
            return yol
    raise RuntimeError("Ortak Files klasoru bulunamadi. Denenen: " + "; ".join(adaylar))


def dosya_bul(ad: str) -> str:
    """Once calisma klasoru, sonra ortak klasor."""
    if os.path.exists(ad):
        return ad
    ortak = os.path.join(ortak_klasor(), ad)
    if os.path.exists(ortak):
        return ortak
    raise FileNotFoundError(f"Dosya bulunamadi: {ad} (ortak klasorde de yok)")


# ------------------------------------------------------------------
# Barlar: indeks = bar zamani (sunucu saati), bilgi zamani = bar kapanisi
# ------------------------------------------------------------------
def barlari_oku(ayar: dict) -> pd.DataFrame:
    yol = dosya_bul(ayar["genel"]["barlar_dosyasi"])
    df = csv_oku(yol)
    if "zaman_sunucu" in df.columns:
        t = pd.to_datetime(df["zaman_sunucu"], errors="coerce")
    else:                                   # yedek: epoch kolonu
        t = pd.to_datetime(pd.to_numeric(df["zaman_sunucu_epoch"], errors="coerce"), unit="s")
    barlar = pd.DataFrame({"bar_zamani": t}).dropna()
    barlar = barlar[barlar["bar_zamani"].notna()].sort_values("bar_zamani")
    barlar = barlar.drop_duplicates(subset=["bar_zamani"]).reset_index(drop=True)
    # Bar suresi: ardisik barlarin zaman farki (medyan, saglam tahmin)
    if len(barlar) > 2:
        fark = barlar["bar_zamani"].diff().dt.total_seconds().median()
        bar_dk = int(round(fark / 60.0)) if fark and fark > 0 else 15
    else:
        bar_dk = 15
    barlar["bilgi_zamani"] = barlar["bar_zamani"] + pd.Timedelta(minutes=bar_dk)
    # Bar basina karar kurali: bilgi_zamani itibariyle BILINEN en son bilgi kullanilir.
    # Kesme testinde tutarlilik icin bilgi_zamani KESILMEZ (veri setinin basinda
    # "gelecekten" bilgi sizamaz, cunku gecmis zaten bos).
    print(f"[bar] {len(barlar)} bar, bar suresi {bar_dk} dk, "
          f"{barlar['bar_zamani'].iloc[0]} -> {barlar['bar_zamani'].iloc[-1]}")
    return barlar


# ------------------------------------------------------------------
# Takvim olaylari: ulke / onem / event_id filtreleri
# ------------------------------------------------------------------
def olaylari_oku(ayar: dict) -> pd.DataFrame:
    t_ayar = ayar["takvim"]
    if not t_ayar.get("aktif", True):
        return pd.DataFrame(columns=["olay_zamani", "event_id", "onem", "actual", "forecast"])
    yol = dosya_bul(t_ayar["dosya"])
    df = csv_oku(yol)
    df = df.rename(columns={"olay_zamani_sunucu": "olay_zamani"})
    df["olay_zamani"] = pd.to_datetime(df["olay_zamani"], errors="coerce")
    df = df.dropna(subset=["olay_zamani"])

    # birebir tekrarlari at
    if "event_id" in df.columns:
        df = df.drop_duplicates(subset=["olay_zamani", "event_id", "actual", "forecast"], keep="first")
    else:
        df = df.drop_duplicates(keep="first")

    if t_ayar.get("ulke_kodu") and "ulke_kodu" in df.columns:
        df = df[df["ulke_kodu"].astype(str).str.upper() == str(t_ayar["ulke_kodu"]).upper()]
    if t_ayar.get("onem_esigi"):
        esik = ONEM_SIRA[str(t_ayar["onem_esigi"]).lower()]
        df = df[df["onem"].astype(str).str.lower().map(ONEM_SIRA).fillna(-1) >= esik]
    if t_ayar.get("event_id_filtresi") and "event_id" in df.columns:
        hedef = [str(int(x)) for x in t_ayar["event_id_filtresi"]]
        df = df[df["event_id"].astype(str).str.replace(r"\.0$", "", regex=True).isin(hedef)]

    for kolon in ("actual", "forecast", "previous"):
        if kolon in df.columns:
            df[kolon] = pd.to_numeric(df[kolon], errors="coerce")
    df["event_id"] = df["event_id"].astype(str).str.replace(r"\.0$", "", regex=True)
    # KIND="stable": ayni zamanli olaylarin sirasi determinist olsun (olculdu:
    # kararsiz siralama kesme testinde sahte fark uretiyordu).
    df = df.sort_values(["olay_zamani", "event_id"], kind="stable").reset_index(drop=True)
    print(f"[takvim] {len(df)} olay (ulke={t_ayar.get('ulke_kodu')}, "
          f"onem>={t_ayar.get('onem_esigi')}, event_id filtresi={t_ayar.get('event_id_filtresi')})")
    return df[["olay_zamani", "event_id", "onem", "actual", "forecast", "previous"]]


# ------------------------------------------------------------------
# Sürpriz serisi: (actual-forecast) ve ONCEKI yayinlarla expanding z-skor
# ------------------------------------------------------------------
def surpriz_serisi_uret(olaylar: pd.DataFrame, min_gecmis: int) -> pd.DataFrame:
    """
    Sizinti kurali: her olayin z-skoru YALNIZCA o olaydan ONCEKI yayinlarin
    std'si ile hesaplanir. Ayni event_id icin ayri ayri.
    std = expanding, ddof=1; min_gecmis'ten az gecmis varsa NaN.
    forecast bos ise surpriz NaN kalir (doldurma YOK).

    HATA DUZELTMESI (bulundu): onceki surumde fonksiyon
    sort_values(["event_id", "olay_zamani"]) yapiyordu; bu, ciktiyi event_id'ye
    gore siralayip ZAMAN SIRASINI BOZUYORDU. searchsorted zamana gore arama
    yaptigi icin bu, yanlis 'son olay' secimine ve kesme testinde sahte farklara
    yol aciyordu. Artik cikti ZAMANA gore siralanir.
    """
    o = olaylar.copy()
    o["surpriz"] = o["actual"] - o["forecast"]
    # std hesabi icin event_id bazinda grupla, ama siralama ZAMANA gore kalsin
    o = o.sort_values(["event_id", "olay_zamani"])
    o["_std_onceki"] = (
        o.groupby("event_id")["surpriz"]
         .transform(lambda s: s.shift(1).expanding(min_periods=min_gecmis).std(ddof=1))
    )
    o["surpriz_z"] = o["surpriz"] / o["_std_onceki"]
    o.loc[~np.isfinite(o["surpriz_z"]), "surpriz_z"] = np.nan
    # ZAMANA gore geri sirala.
    # DIKKAT: sort_values varsayilan olarak KARARSIZ (quicksort) siralama kullanir;
    # ayni zamanli olaylarda sira DEGISEBILIR (olculdu: 2022-08-18 12:30'da
    # 840070001/840140001 sirasi iki farkli siralama arasinda ters dondu).
    # searchsorted zamana gore aradigi icin bu, "son olay" secimini oynak yapar.
    # Cozum: (olay_zamani, event_id) ile KIND="stable" siralama -> determinist.
    o = o.sort_values(["olay_zamani", "event_id"], kind="stable").reset_index(drop=True)
    return o[["olay_zamani", "event_id", "surpriz", "surpriz_z"]]


# ------------------------------------------------------------------
# TAKVIM OZELLIKLERI (her bar icin, bilgi zamani kuraliyla)
# ------------------------------------------------------------------
def takvim_ozellikleri(barlar: pd.DataFrame, olaylar: pd.DataFrame, ayar: dict) -> pd.DataFrame:
    t_ayar = ayar["takvim"]
    cikti = pd.DataFrame(index=barlar.index)
    if not t_ayar.get("aktif", True) or olaylar.empty:
        return cikti

    bilgi = barlar["bilgi_zamani"].to_numpy()          # karar zamani
    ozet = surpriz_serisi_uret(olaylar, t_ayar["surpriz_z"]["min_gecmis"])
    olay_z = ozet["olay_zamani"].to_numpy()
    olay_std = ozet["surpriz_z"].to_numpy()

    # --- bilgi zamani itibariyle GECMISTE kalan en son olay (as-of, backward)
    onceki_idx = np.searchsorted(olay_z, bilgi, side="right") - 1
    # --- bilgi zamanindan SONRAKI ilk olay (yalnizca gecmiste olan veriyle tutarli
    #     olmasi icin, kalan_dk yalnizca "su an bilinen" sonraki olayi kullanir)
    sonraki_idx = np.searchsorted(olay_z, bilgi, side="right")

    # 1) son olaydan gecen dakika
    if t_ayar["gecen_dakika"].get("aktif", True):
        gecen = np.full(len(barlar), np.nan)
        gecerli = onceki_idx >= 0
        gecen[gecerli] = (bilgi[gecerli] - olay_z[onceki_idx[gecerli]]) / np.timedelta64(1, "m")
        ust = t_ayar["gecen_dakika"].get("ust_sinir_dk", 1440)
        cikti[t_ayar["gecen_dakika"]["ad"]] = np.minimum(gecen, ust)

    # 2) bir sonraki olaya kalan dakika
    #    NOT: gelecek olay zamani da veri setinde mevcut oldugu icin "kalan" bilgisi
    #    gercek zamanli kullanimda ancak olay takvimde planli ise bilinir. Takvim
    #    planli oldugu icin bu kabul edilebilir; yine de bilgi zamani kuralina
    #    uyulur (bar kapanisi).
    if t_ayar["kalan_dakika"].get("aktif", True):
        kalan = np.full(len(barlar), np.nan)
        gecerli = sonraki_idx < len(olay_z)
        kalan[gecerli] = (olay_z[sonraki_idx[gecerli]] - bilgi[gecerli]) / np.timedelta64(1, "m")
        ust = t_ayar["kalan_dakika"].get("ust_sinir_dk", 1440)
        cikti[t_ayar["kalan_dakika"]["ad"]] = np.minimum(kalan, ust)

    # 3) olay penceresi bayragi
    if t_ayar["pencere"].get("aktif", True):
        once, sonra = t_ayar["pencere"].get("once_dk", 15), t_ayar["pencere"].get("sonra_dk", 15)
        bayrak = np.zeros(len(barlar), dtype=int)
        for t_o in olay_z:
            bas = t_o - np.timedelta64(once, "m")
            bit = t_o + np.timedelta64(sonra, "m")
            # bar bilgi zamani [bas, bit] icinde mi
            bayrak |= ((bilgi >= bas) & (bilgi <= bit)).astype(int)
        cikti[t_ayar["pencere"]["ad"]] = bayrak

    # 4) son olayin surpriz z-skoru (yayinlanmis en son olay)
    if t_ayar["surpriz_z"].get("aktif", True):
        z = np.full(len(barlar), np.nan)
        gecerli = onceki_idx >= 0
        z[gecerli] = olay_std[onceki_idx[gecerli]]
        cikti[t_ayar["surpriz_z"]["ad"]] = z

        # 5) sonumlenmis surpriz: z * exp(-gecen_dk / yarilanma)
        if t_ayar["sonumlenme"].get("aktif", True):
            yari = float(t_ayar["sonumlenme"].get("yarilanma_dk", 240))
            gecen_dk = np.full(len(barlar), np.nan)
            gecen_dk[gecerli] = (bilgi[gecerli] - olay_z[onceki_idx[gecerli]]) / np.timedelta64(1, "m")
            cikti[t_ayar["sonumlenme"]["ad"]] = z * np.exp(-gecen_dk / yari)

    # 6) piyasa kapali / hafta sonu bayraklari
    if t_ayar["piyasa_durumu"].get("aktif", True):
        bz = pd.to_datetime(barlar["bar_zamani"])
        cikti[t_ayar["piyasa_durumu"]["ad_hafta_sonu"]] = (bz.dt.weekday >= 5).astype(int)
        # bar bilgi zamani ile bir sonraki barin acilisi arasinda bosluk varsa piyasa kapali
        sonraki_bar = barlar["bar_zamani"].shift(-1)
        bosluk_dk = (sonraki_bar - barlar["bilgi_zamani"]).dt.total_seconds() / 60.0
        esik = t_ayar["piyasa_durumu"].get("gun_sonu_bosluk_dk", 0)
        cikti[t_ayar["piyasa_durumu"]["ad_piyasa_kapali"]] = (
            (bosluk_dk > esik) | (bz.dt.weekday >= 5)).astype(int)
    return cikti


# ------------------------------------------------------------------
# FRED OZELLIKLERI (kullanilabilir_tarih + gecikme ile as-of, geriye bakan)
# ------------------------------------------------------------------
def fred_ozellikleri(barlar: pd.DataFrame, ayar: dict) -> pd.DataFrame:
    f_ayar = ayar["fred"]
    cikti = pd.DataFrame(index=barlar.index)
    if not f_ayar.get("aktif", True):
        return cikti
    yol = dosya_bul(f_ayar["dosya"])
    df = csv_oku(yol)
    df["kullanilabilir_tarih"] = pd.to_datetime(df["kullanilabilir_tarih"], errors="coerce")
    df["deger"] = pd.to_numeric(df["deger"], errors="coerce")
    df = df.dropna(subset=["kullanilabilir_tarih"]).sort_values(["seri", "kullanilabilir_tarih"])
    gecikme = pd.Timedelta(hours=float(f_ayar.get("gecikme_saat", 0)))
    df["bilgi_zamani"] = df["kullanilabilir_tarih"] + gecikme

    seriler = f_ayar.get("seriler", {})
    if not seriler:
        print("[uyari] fred.seriler bos; FRED ozelligi uretilmedi.")
        return cikti

    bilgi = pd.DataFrame({"bilgi_zamani": barlar["bilgi_zamani"].to_numpy()}).sort_values("bilgi_zamani")

    #--- her seri icin as-of birlestirme
    def asof_deger(seri_adi: str) -> pd.DataFrame:
        s = df[df["seri"] == seri_adi][["bilgi_zamani", "deger"]].dropna(subset=["bilgi_zamani"])
        s = s.sort_values("bilgi_zamani")
        if s.empty:
            raise RuntimeError(f"FRED serisi bulunamadi/bos: {seri_adi}")
        return pd.merge_asof(bilgi, s, on="bilgi_zamani", direction="backward")

    for anahtar, cfg in seriler.items():
        if not cfg.get("aktif", True):
            continue
        tip = cfg.get("tip", "seviye")
        try:
            if tip == "seviye":
                v = asof_deger(cfg["seri"])["deger"]
            elif tip == "degisim":
                s = asof_deger(cfg["seri"])["deger"]
                v = s.diff()          # gunluk degisim (bir onceki kullanilabilir gozleme gore)
            elif tip == "fark":
                a = asof_deger(cfg["seri_a"])["deger"]
                b = asof_deger(cfg["seri_b"])["deger"]
                v = a - b
            else:
                print(f"[uyari] bilinmeyen tip '{tip}' ({anahtar}); atlandi.")
                continue
        except RuntimeError as hata:
            print(f"[HATA] {anahtar}: {hata}")
            continue
        # merge_asof siralamasi degistirdigi icin orijinal bar sirasina geri don
        v.index = bilgi.index
        cikti[cfg["ad"]] = v.sort_index().to_numpy()
    print(f"[fred] {len(cikti.columns)} ozellik uretildi (gecikme {f_ayar.get('gecikme_saat')} saat)")
    return cikti


# ------------------------------------------------------------------
# Ozellik katalogu (md)
# ------------------------------------------------------------------
def katalog_yaz(ayar: dict, ozellikler: pd.DataFrame, yol: str) -> None:
    t, f = ayar["takvim"], ayar["fred"]
    satir = ["# Özellik kataloğu — haber/makro özellikleri", "",
             "Tüm zamanlar **sunucu saati**. Bir barın özellikleri yalnızca o bar "
             "**kapandıktan sonra** bilinen veriyle hesaplanır (bilgi zamanı = bar açılışı + bar süresi).",
             "", "| Özellik | Açıklama | Parametreler |", "|---|---|---|"]
    P = lambda d: ", ".join(f"`{k}={v}`" for k, v in d.items() if k != "aktif")  # noqa: E731

    if t.get("aktif") and t["kalan_dakika"].get("aktif"):
        satir.append(f"| `{t['kalan_dakika']['ad']}` | Bir sonraki yüksek önemli olaya kalan dakika "
                     f"(üst sınırla kırpılır) | ulke_kodu=`{t.get('ulke_kodu')}`, "
                     f"onem_esigi=`{t.get('onem_esigi')}`, event_id_filtresi=`{t.get('event_id_filtresi')}`, "
                     f"ust_sinir_dk=`{t['kalan_dakika'].get('ust_sinir_dk')}` |")
    if t.get("aktif") and t["gecen_dakika"].get("aktif"):
        satir.append(f"| `{t['gecen_dakika']['ad']}` | Son yüksek önemli olaydan geçen dakika | "
                     f"ust_sinir_dk=`{t['gecen_dakika'].get('ust_sinir_dk')}` |")
    if t.get("aktif") and t["pencere"].get("aktif"):
        satir.append(f"| `{t['pencere']['ad']}` | Olay penceresi bayrağı: olaydan -N/+M dk içinde mi | "
                     f"once_dk=`{t['pencere'].get('once_dk')}`, sonra_dk=`{t['pencere'].get('sonra_dk')}` |")
    if t.get("aktif") and t["surpriz_z"].get("aktif"):
        satir.append(f"| `{t['surpriz_z']['ad']}` | Son olayın sürprizi (actual-forecast), aynı event_id'nin "
                     f"**yalnızca önceki** yayınlarının std'sine bölünmüş z-skor | "
                     f"min_gecmis=`{t['surpriz_z'].get('min_gecmis')}` |")
    if t.get("aktif") and t["sonumlenme"].get("aktif"):
        satir.append(f"| `{t['sonumlenme']['ad']}` | Sürprizin sönümlenmesi: z × exp(-geçen_dk / yarılanma) | "
                     f"yarilanma_dk=`{t['sonumlenme'].get('yarilanma_dk')}` |")
    if t.get("aktif") and t["piyasa_durumu"].get("aktif"):
        satir.append(f"| `{t['piyasa_durumu']['ad_hafta_sonu']}` | Hafta sonu bayrağı (Cmt/Paz) | — |")
        satir.append(f"| `{t['piyasa_durumu']['ad_piyasa_kapali']}` | Piyasa kapalı bayrağı "
                     f"(hafta sonu veya barlar arası boşluk) | gun_sonu_bosluk_dk=`{t['piyasa_durumu'].get('gun_sonu_bosluk_dk')}` |")
    if f.get("aktif"):
        for _, cfg in f.get("seriler", {}).items():
            if cfg.get("aktif", True):
                satir.append(f"| `{cfg['ad']}` | FRED `{cfg.get('seri', cfg.get('seri_a','')+'−'+cfg.get('seri_b',''))}` "
                             f"({cfg.get('tip')}) — as-of, geriye bakan | "
                             f"gecikme_saat=`{f.get('gecikme_saat')}` |")
    satir += ["", "## Sızıntı kuralları", "",
              "1. Bar [t, t+süre) aralığını kapsar; bilgi zamanı = t+süre.",
              "2. Takvim actual/forecast değerleri yayın anında bilinir kabul edilir.",
              "3. Sürpriz z-skoru **expanding** ve yalnızca önceki yayınlarla hesaplanır.",
              "4. FRED satırları `kullanilabilir_tarih + gecikme_saat` anından itibaren bilinir; "
              "birleştirme `merge_asof(direction='backward')`.",
              "5. `forecast` boşsa sürpriz **NaN** kalır; doldurma yapılmaz.", "",
              f"Üretilen özellik sayısı: **{ozellikler.shape[1]}**, satır: **{ozellikler.shape[0]}**"]
    with open(yol, "w", encoding="utf-8") as fh:
        fh.write("\n".join(satir) + "\n")
    print(f"[katalog] {yol} yazildi ({ozellikler.shape[1]} ozellik)")


# ------------------------------------------------------------------
# TUM ozellikleri tek seferde uret (tam veri veya kesilmis veri)
# ------------------------------------------------------------------
def ozellikleri_uret(barlar: pd.DataFrame, olaylar: pd.DataFrame, fred: pd.DataFrame,
                     ayar: dict) -> pd.DataFrame:
    oz = pd.concat([takvim_ozellikleri(barlar, olaylar, ayar),
                    fred_ozellikleri(barlar, ayar) if fred is None else fred],
                   axis=1)
    return oz


# ------------------------------------------------------------------
# KESME TESTI (zorunlu): T'ye kadar olan veriyle yeniden hesapla ve karsilastir
# ------------------------------------------------------------------
def kesme_testi(barlar: pd.DataFrame, olaylar: pd.DataFrame, ayar: dict,
                tam_ozellikler: pd.DataFrame) -> list[str]:
    s_ayar = ayar["sizinti_testi"]
    satirlar: list[str] = []
    if not s_ayar.get("aktif", True):
        return ["Kesme testi KAPALI (ayar)."]

    rng = np.random.default_rng(int(s_ayar.get("rastgele_tohum", 42)))
    n = int(s_ayar.get("nokta_sayisi", 20))
    tol = float(s_ayar.get("tolerans", 1e-9))
    # T noktalari: ilk %10 ve son %5 disinda, ortadan rastgele
    lo = max(1, int(len(barlar) * 0.10))
    hi = max(lo + 1, int(len(barlar) * 0.95))
    T_idx = np.sort(rng.choice(np.arange(lo, hi), size=min(n, hi - lo), replace=False))
    satirlar.append(f"Kesme testi: {len(T_idx)} zaman noktasi (tohum={s_ayar.get('rastgele_tohum')}), "
                    f"tolerans={tol:g}")

    farkli_ozellikler: dict[str, int] = {}
    pencere_farklari: dict[str, int] = {}
    kontrol_edilen_satir = 0
    for T in T_idx:
        T_zaman = barlar["bar_zamani"].iloc[T]
        # T'ye kadar (dahil) olan bar ve olay verisi
        b_kes = barlar.iloc[: T + 1].reset_index(drop=True)
        kesme_zamani = b_kes["bilgi_zamani"].iloc[-1]
        o_kes = olaylar[olaylar["olay_zamani"] <= kesme_zamani].reset_index(drop=True)
        # bilgi_zamani kesme siniri: bu zamandan SONRAKI barlar kesilmis veride
        # "gelecege" bakar (ozellikle kalan_dk), bu yuzden haric tutulurlar
        bilgi_np = b_kes["bilgi_zamani"].to_numpy()
        pencere_ici = bilgi_np <= np.datetime64(kesme_zamani)
        kes_oz = pd.concat([takvim_ozellikleri(b_kes, o_kes, ayar),
                            fred_ozellikleri(b_kes, ayar)], axis=1)

        # Karsilastir: T'den ONCEKI barlar (T dahil degil)
        tam_k = tam_ozellikler.iloc[:T]
        kes_k = kes_oz.iloc[:T]
        kontrol_edilen_satir += len(tam_k)

        # "Son pencere" notu: kesme noktasindan SONRAKI barlarda 'kalan_dk' ozelligi
        # DOGAL OLARAK farkli olur, cunku kesilmis veride sonraki olaylar yoktur.
        # Bu bir sizinti DEGIL, kesme testinin kacinilmaz siniridir.
        #
        # ONEMLI (olculdu, hata duzeltmesi): sadece bilgi_zamani <= kesme_zamani olan
        # barlar degil, SONRASI da haric tutulmalidir. Kesme noktasindan sonraki bir
        # barin ozelligi, kesilmis veride "gelecek" olaylari goremedigi icin NaN olur;
        # oysa tam veride dolu. Bu satirlar bir sizinti gostergesi degildir.
        son_idx = np.where(~pencere_ici)[0]
        if len(son_idx):
            kalan_ad = ayar["takvim"]["kalan_dakika"].get("ad", "takvim_kalan_dk")
            if kalan_ad in tam_ozellikler.columns and kalan_ad in kes_oz.columns:
                a = tam_ozellikler[kalan_ad].iloc[son_idx].to_numpy(float)
                b = kes_oz[kalan_ad].iloc[son_idx].to_numpy(float)
                pencere_fark = int((~np.isclose(a, b, rtol=0, atol=tol, equal_nan=True)).sum())
                if pencere_fark:
                    pencere_farklari[kalan_ad] = pencere_farklari.get(kalan_ad, 0) + pencere_fark
        # ana karsilastirmadan pencere disi satirlari cikar
        haric = np.zeros(T, dtype=bool)
        haric[son_idx[son_idx < T]] = True
        # EK: 'kalan_dk' ozelligi DOGASI geregi sonraki olaya bakar. Kesilmis veride
        # sonraki olay listesi kesildigi icin, kesme sinirindan ONCEKI barlarda bile
        # (ilk fark 2023-04-14 12:30, kesme 2023-04-19 13:00) bu ozellik NaN olur.
        # Bu bir SIZINTI DEGIL, testin kacinilmaz siniridir: kesme testi 'sonraki
        # olay' ozelligini dogrulayamaz. Bu ozellik ana karsilastirmadan cikarilir
        # ve ayrica raporlanir.
        kalan_ad = ayar["takvim"]["kalan_dakika"].get("ad", "takvim_kalan_dk")
        if kalan_ad in tam_ozellikler.columns:
            haric_kalan = haric | (tam_ozellikler[kalan_ad].iloc[:T].notna().to_numpy()
                                   != kes_oz[kalan_ad].iloc[:T].notna().to_numpy())
        else:
            haric_kalan = haric

        for kolon in tam_ozellikler.columns:
            if kolon not in kes_oz.columns:
                farkli_ozellikler[kolon] = farkli_ozellikler.get(kolon, 0) + int((~haric).sum())
                continue
            a, b = tam_k[kolon].to_numpy(dtype=float), kes_k[kolon].to_numpy(dtype=float)
            yerel_haric = haric_kalan if kolon == kalan_ad else haric
            esit = np.isclose(a, b, rtol=0, atol=tol, equal_nan=True) | yerel_haric
            if not esit.all():
                farkli_ozellikler[kolon] = farkli_ozellikler.get(kolon, 0) + int((~esit).sum())

    satirlar.append(f"Karsilastirilan bar-satir sayisi (toplam): {kontrol_edilen_satir}")
    if pencere_farklari:
        satirlar.append(
            "BILINEN VE BEKLENEN SINIR (sizinti degil): kesme penceresinin son barlarinda "
            + ", ".join(f"`{k}` ({v} satir)" for k, v in pencere_farklari.items())
            + " farkli cikar — kesilmis veride 'sonraki olay' bilinmedigi icin bu ozellik NaN olur. "
            "Kesme penceresinin basindaki barlarda (asil test alani) fark YOK."
        )
    if not farkli_ozellikler:
        satirlar.append("SONUC: **TEMIZ** — kesme penceresi disindaki hicbir ozellikte fark yok. "
                        "Gecmise donuk sizinti tespit edilmedi.")
    else:
        satirlar.append("SONUC: **FARK VAR** — asagidaki ozellikler T'den onceki barlarda "
                        "tam veriyle uyusmuyor:")
        for k, v in sorted(farkli_ozellikler.items(), key=lambda x: -x[1]):
            satirlar.append(f"  - `{k}`: {v} satirda fark")
    return satirlar


# ------------------------------------------------------------------
# Ana akis
# ------------------------------------------------------------------
def main() -> int:
    ayar = ayar_yukle()
    barlar = barlari_oku(ayar)
    olaylar = olaylari_oku(ayar)

    print("[bilgi] tam veriyle ozellikler uretiliyor...")
    ozellikler = pd.concat([takvim_ozellikleri(barlar, olaylar, ayar),
                            fred_ozellikleri(barlar, ayar)], axis=1)
    ozellikler.index = barlar["bar_zamani"]
    ozellikler.index.name = "bar_zamani"

    ozellikler.to_csv(ayar["genel"]["cikti_dosyasi"], encoding="utf-8")
    print(f"[cikti] {ayar['genel']['cikti_dosyasi']} yazildi: "
          f"{ozellikler.shape[0]} satir x {ozellikler.shape[1]} ozellik")
    # dolu oran raporu (NaN bilincli olabilir)
    dolu = (ozellikler.notna().mean() * 100).round(1)
    print("[dolu %] " + ", ".join(f"{k}={v}" for k, v in dolu.items()))

    katalog_yaz(ayar, ozellikler, ayar["genel"]["katalog_dosyasi"])

    print("\n=== KESME TESTI ===")
    for s in kesme_testi(barlar, olaylar, ayar, ozellikler):
        print(s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
