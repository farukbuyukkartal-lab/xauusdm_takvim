#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADIM 4: Fayda testi (haber/makro ozellikleri ise yariyor mu?)
============================================================
Model URETIM kodunu DEGISTIRMEZ. features.py / labeling.py yalnizca IMPORT edilir.

DENEYLER (ayni bolmeler, ayni tohumlar):
  A) yalniz fiyat            (features.py 24 ozellik)
  B) fiyat + takvim
  C) fiyat + FRED
  D) fiyat + hepsi
  E) kontrol: D ama haber kolonlari EGITIM setinde zaman bloklariyla karistirilmis
  F) D ama takvim_kalan_dk CIKARILMIS (ablasyon)
  G) D'nin esleme gecikmesi duyarliligi: 0 / 15 / 30 dk

BOLME: genisleyen pencereli walk-forward (5-6 kat), etiket ufku kadar embargo.
KILIT: son 6 ay (2026-04-17 sonrasi) varsayilan olarak OKUNMAZ; yalnizca
       fayda_ayar.yaml -> kilit.kilidi_ac=true ile acilir.

METRIKLER: makro-F1, log-loss, basit maliyetli simulasyon; uc dilimde
(tum barlar / olay penceresi / olay disi). 5 tohum ort +- std; blok bootstrap CI.

CIKTI: fayda_raporu.md + deneyler/<deney>_<tohum>.json

ISARETLER: [GERCEK VERI] / [SENTETIK] / [CALISTIRILMADI]
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from datetime import datetime

import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import f1_score, log_loss
from sklearn.preprocessing import StandardScaler

# ===================== AYARLAR (en ustte) ==========================
AYAR_DOSYASI = "fayda_ayar.yaml"
VARSAYILAN = {
    "veri": {"barlar_dosyasi": "bars_mql5.csv", "haber_dosyasi": "haber_ozellikleri.csv",
             "model_kodu_klasoru": "", "etiket_ufku": 32},
    "kilit": {"kilidi_ac": False, "kilit_baslangici": "2026-04-17"},
    "bolme": {"tip": "walk_forward", "kat_sayisi": 6, "ilk_egitim_orani": 0.35,
              "embargo_bar": 32, "test_orani": 0.10},
    "model": {"tip": "auto", "n_estimators": 200, "learning_rate": 0.08, "max_depth": 6,
              "max_iter_hgb": 200, "egitim_alt_ornek": None,
              "rastgele_tohumlar": [11, 22, 33, 44, 55], "olcekleme": "standard",
              "n_jobs": 4, "blas_thread_limit": 2},
    "metrikler": {"makro_f1": True, "log_loss": True,
                  "simulasyon": {"aktif": True, "spread_usd": 0.25, "komisyon_usd": 0.0,
                                 "esik": 0.5, "tutma_bari": 32}},
    "dilimler": {"olay_once_saat": 1, "olay_sonra_saat": 4},
    "bootstrap": {"aktif": True, "blok_uzunlugu": 96, "tekrar": 500, "guven": 0.95},
    "hiz_testi": {"aktif": True, "alt_ornek": 15000, "kat_sayisi": 2},
}
HABER_TAKVIM = ["takvim_gecen_dk", "takvim_kalan_dk", "takvim_pencere", "takvim_surpriz_z",
                "takvim_surpriz_z_sonumlu", "takvim_hafta_sonu", "takvim_piyasa_kapali"]
HABER_FRED = ["fred_dfii10_degisim", "fred_t10yie_degisim", "fred_dgs10_dgs2_fark",
              "fred_vix_seviye", "fred_vix_degisim"]
# ===================================================================


# ------------------------------------------------------------------
def ayar_yukle(yol: str = AYAR_DOSYASI) -> dict:
    def birlestir(temel, gelen):
        sonuc = dict(temel)
        for k, v in (gelen or {}).items():
            sonuc[k] = birlestir(temel[k], v) if isinstance(temel.get(k), dict) and isinstance(v, dict) else v
        return sonuc
    if not os.path.exists(yol):
        print(f"[uyari] {yol} yok; varsayilan ayarlar.")
        return VARSAYILAN
    with open(yol, encoding="utf-8") as f:
        return birlestir(VARSAYILAN, yaml.safe_load(f) or {})


def csv_oku(yol: str) -> pd.DataFrame:
    for k in ("utf-8-sig", "utf-8", "cp1254", "latin-1"):
        try:
            return pd.read_csv(yol, encoding=k)
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"CSV okunamadi: {yol}")


def ortak_klasor() -> str:
    adaylar = []
    env = os.environ.get("TERMINAL_COMMON_DATA_PATH")
    if env:
        adaylar.append(os.path.join(env, "Files"))
    appdata = os.environ.get("APPDATA")
    if appdata:
        adaylar.append(os.path.join(appdata, "MetaQuotes", "Terminal", "Common", "Files"))
    for y in adaylar:
        if os.path.isdir(y):
            return y
    raise RuntimeError("Ortak Files klasoru bulunamadi.")


def dosya_bul(ad: str) -> str:
    if os.path.exists(ad):
        return ad
    y = os.path.join(ortak_klasor(), ad)
    if os.path.exists(y):
        return y
    raise FileNotFoundError(f"Dosya yok: {ad}")


# ------------------------------------------------------------------
# Model kodunu IMPORT et (degistirmeden): features.py + labeling.py
# ------------------------------------------------------------------
def model_kodunu_yukle(klasor: str):
    if not klasor or not os.path.isdir(klasor):
        raise RuntimeError(
            f"model_kodu_klasoru bulunamadi: '{klasor}'. fayda_ayar.yaml -> veri.model_kodu_klasoru "
            "degerini features.py/labeling.py'nin bulundugu klasore ayarlayin."
        )
    yollar = {}
    for ad in ("features", "labeling"):
        yol = os.path.join(klasor, f"{ad}.py")
        if not os.path.exists(yol):
            raise RuntimeError(f"{ad}.py bulunamadi: {yol}")
        spec = importlib.util.spec_from_file_location(f"xau_{ad}", yol)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        yollar[ad] = mod
    return yollar["features"], yollar["labeling"]


# ------------------------------------------------------------------
# Veri: barlar + fiyat ozellikleri + etiketler + haber ozellikleri
# ------------------------------------------------------------------
def veriyi_hazirla(ayar: dict) -> pd.DataFrame:
    feats, labels = model_kodunu_yukle(ayar["veri"]["model_kodu_klasoru"])

    bar_yolu = dosya_bul(ayar["veri"]["barlar_dosyasi"])
    b = csv_oku(bar_yolu)
    b = b.dropna(subset=["zaman_sunucu_epoch"])
    b["time"] = pd.to_datetime(pd.to_numeric(b["zaman_sunucu_epoch"], errors="coerce"), unit="s")
    b = b.dropna(subset=["time"]).sort_values("time").drop_duplicates(subset=["time"])
    for k in ("open", "high", "low", "close", "tick_volume"):
        b[k] = pd.to_numeric(b[k], errors="coerce")
    b = b.set_index("time")[["open", "high", "low", "close", "tick_volume"]]
    print(f"[veri] {len(b)} bar: {b.index[0]} -> {b.index[-1]}")

    # KILIT: son 6 ay okunmaz (varsayilan)
    kilit_t = pd.Timestamp(ayar["kilit"]["kilit_baslangici"])
    if not ayar["kilit"]["kilidi_ac"]:
        onceki = len(b)
        b = b[b.index < kilit_t]
        print(f"[kilit] {kilit_t} ve sonrasi CIKARILDI ({onceki} -> {len(b)} bar). "
              "Acmak icin: fayda_ayar.yaml -> kilit.kilidi_ac: true")
    else:
        print(f"[kilit] ACIK! {kilit_t} sonrasi dahil edildi ({len(b)} bar).")

    # Fiyat ozellikleri (mevcut features.py v2, aynen)
    Xf = feats.prepare_features_full(b)
    print(f"[ozellik] fiyat ozellikleri: {Xf.shape[1]} kolon, {len(Xf)} satir "
          f"(features.NUM_FEATURES={getattr(feats,'NUM_FEATURES','?')})")

    # Etiketler (mevcut labeling.py, aynen)
    y = labels.compute_action_labels(b, horizon=int(ayar["veri"]["etiket_ufku"]))
    y = y.loc[Xf.index]
    print(f"[etiket] sinif dagilimi: {y.value_counts().sort_index().to_dict()}")

    # Haber ozellikleri (haber_ozellikleri.py cikti)
    h = csv_oku(dosya_bul(ayar["veri"]["haber_dosyasi"]))
    h["time"] = pd.to_datetime(h["bar_zamani"], errors="coerce")
    h = h.dropna(subset=["time"]).set_index("time").drop(columns=["bar_zamani"])
    Xh = h.reindex(Xf.index)
    dolu = (Xh.notna().mean() * 100).round(1)
    print(f"[ozellik] haber ozellikleri: {Xh.shape[1]} kolon, dolu %: {dolu.to_dict()}")

    df = pd.concat([Xf, Xh], axis=1)
    df["y"] = y.astype(int)
    # NaN'siz satirlar (fiyat tarafi warmup sonrasi tam; haber NaN'lari 0 ile doldurulur
    # ve ayri bir "eksik" bayragi eklenir -> agac modeli bunu kullanabilir)
    eksik_kolonlar = [f"{c}_eksik" for c in Xh.columns]
    eksik = Xh.isna().astype(int)
    eksik.columns = eksik_kolonlar
    df = pd.concat([df, eksik], axis=1)
    df[Xh.columns] = df[Xh.columns].fillna(0.0)
    df = df.dropna(subset=[c for c in Xf.columns])
    print(f"[veri] birlesik: {df.shape[0]} satir x {df.shape[1]} kolon")
    return df


# ------------------------------------------------------------------
# Walk-forward bolmeler (embargo/purge ile)
# ------------------------------------------------------------------
def bolmeler(df: pd.DataFrame, ayar: dict) -> list[dict]:
    n = len(df)
    kat = int(ayar["bolme"]["kat_sayisi"])
    ilk_oran = float(ayar["bolme"]["ilk_egitim_orani"])
    emb = int(ayar["bolme"]["embargo_bar"])
    test_oran = float(ayar["bolme"]["test_orani"])

    ilk_egitim = int(n * ilk_oran)
    kalan = n - ilk_egitim
    test_boy = max(1, int(kalan / kat)) if test_oran <= 0 else max(1, int(n * test_oran))
    bolmeler_liste = []
    bas = ilk_egitim
    while bas + test_boy <= n and len(bolmeler_liste) < kat:
        egitim_bitis = bas - emb                       # embargo: egitim ile test arasinda bosluk
        if egitim_bitis <= 0:
            bas += test_boy
            continue
        bolmeler_liste.append({
            "egitim": (0, egitim_bitis),
            "test": (bas, min(bas + test_boy, n)),
        })
        bas += test_boy
    print(f"[bolme] walk-forward {len(bolmeler_liste)} kat, embargo={emb} bar")
    for i, b in enumerate(bolmeler_liste):
        print(f"   kat {i+1}: egitim {b['egitim']} ({b['egitim'][1]-b['egitim'][0]}), "
              f"test {b['test']} ({b['test'][1]-b['test'][0]})")
    return bolmeler_liste


# ------------------------------------------------------------------
# Model: LightGBM varsa onu, yoksa sklearn HistGradientBoosting
# ------------------------------------------------------------------
def model_olustur(ayar: dict, tohum: int):
    m = ayar["model"]
    tip = m.get("tip", "auto")
    if tip in ("auto", "lightgbm"):
        try:
            import lightgbm as lgb  # noqa: PLC0415
            return lgb.LGBMClassifier(
                n_estimators=int(m["n_estimators"]), learning_rate=float(m["learning_rate"]),
                max_depth=int(m["max_depth"]), random_state=tohum, verbose=-1,
                num_leaves=15, min_child_samples=int(m.get("min_samples_leaf", 200)),
                reg_lambda=float(m.get("l2", 1.0)),
            ), "lightgbm"
        except ImportError:
            if tip == "lightgbm":
                raise RuntimeError("lightgbm istenmis ama kurulu degil.")
    return HistGradientBoostingClassifier(
        max_iter=int(m["max_iter_hgb"]), learning_rate=float(m["learning_rate"]),
        max_depth=int(m["max_depth"]), random_state=tohum,
        early_stopping=False,                       # zaman serisinde sizintili dogrulamayi kapat
        min_samples_leaf=int(m.get("min_samples_leaf", 200)),
        l2_regularization=float(m.get("l2", 1.0)),
    ), "sklearn_hist"


# ------------------------------------------------------------------
# Metrikler
# ------------------------------------------------------------------
def simulasyon(y_true: np.ndarray, proba: np.ndarray, kapanis: np.ndarray,
               ayar: dict) -> dict:
    """
    Basit maliyetli simulasyon: her bar icin en yuksek olasilikli sinif secilir;
    BUY/SELL_SHORT ise tutma_bari sonra kapanis fiyatindan cikilir.
    Maliyet = spread + komisyon (USD/ons, islem basina).
    Getiri yalnizca kapanmis islemler uzerinden toplanir.

    kapanis: test dilimine ait KAPANIS fiyatlari (ayni uzunlukta, sira ile hizali).
    """
    s = ayar["metrikler"]["simulasyon"]
    esik = float(s["esik"]); tut = int(s["tutma_bari"])
    maliyet = float(s["spread_usd"]) + float(s["komisyon_usd"])
    sinif = np.argmax(proba, axis=1)
    en_yuksek = proba.max(axis=1)
    getiriler = []
    n = len(sinif)
    for i in range(n - tut):
        if en_yuksek[i] < esik:
            continue
        c = sinif[i]
        if c == 1:      # BUY
            g = kapanis[i + tut] - kapanis[i]
        elif c == 2:    # SELL_SHORT
            g = kapanis[i] - kapanis[i + tut]
        else:
            continue    # HOLD / CLOSE_* -> islem yok
        getiriler.append(g - maliyet)
    if not getiriler:
        return {"islem": 0, "toplam_usd": 0.0, "ort_usd": 0.0, "isabet_orani": float("nan")}
    g = np.asarray(getiriler)
    return {"islem": int(len(g)), "toplam_usd": float(g.sum()), "ort_usd": float(g.mean()),
            "isabet_orani": float((g > 0).mean())}


def metrikler_hesapla(y_true, proba, kapanis, ayar) -> dict:
    out = {}
    try:
        out["makro_f1"] = float(f1_score(y_true, np.argmax(proba, axis=1),
                                         average="macro", zero_division=0))
    except Exception:
        out["makro_f1"] = float("nan")
    try:
        out["log_loss"] = float(log_loss(y_true, proba, labels=[0, 1, 2, 3, 4]))
    except Exception:
        out["log_loss"] = float("nan")
    if ayar["metrikler"]["simulasyon"]["aktif"]:
        out.update(simulasyon(y_true, proba, kapanis, ayar))
    return out


def blok_bootstrap_ci(a: np.ndarray, b: np.ndarray, ayar: dict, tohum: int = 0):
    """a - b farki icin blok bootstrap guven araligi."""
    bs = ayar["bootstrap"]
    if not bs.get("aktif", True) or len(a) < 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(tohum)
    L = int(bs["blok_uzunlugu"]); n = len(a)
    nblok = int(np.ceil(n / L))
    farklar = np.empty(int(bs["tekrar"]))
    d = a - b
    for r in range(int(bs["tekrar"])):
        baslangiclar = rng.integers(0, max(1, n - L + 1), size=nblok)
        sec = np.concatenate([np.arange(s, min(s + L, n)) for s in baslangiclar])[:n]
        farklar[r] = np.nanmean(d[sec])
    alfa = (1 - float(bs["guven"])) / 2
    return (float(np.nanquantile(farklar, alfa)), float(np.nanquantile(farklar, 1 - alfa)))


# ------------------------------------------------------------------
# Bir deneyi kos
# ------------------------------------------------------------------
def deney_kos(ad: str, kolonlar: list[str], df: pd.DataFrame, ayar: dict,
              bolmeler_liste: list[dict], tohum: int, karistir_haber: bool = False) -> dict:
    feats = kolonlar
    kat_metrikleri = []
    tum_y, tum_p, tum_idx = [], [], []
    for b in bolmeler_liste:
        e0, e1 = b["egitim"]; t0, t1 = b["test"]
        egitim = df.iloc[e0:e1]
        test = df.iloc[t0:t1]

        X_tr = egitim[feats].to_numpy(float)
        y_tr = egitim["y"].to_numpy(int)
        X_te = test[feats].to_numpy(float)
        y_te = test["y"].to_numpy(int)

        # E) kontrol: haber kolonlari EGITIM setinde zaman bloklariyla karistirilir
        if karistir_haber:
            haber_idx = [feats.index(c) for c in feats if c.startswith(("takvim_", "fred_"))]
            if haber_idx:
                rng = np.random.default_rng(tohum)
                blok = max(1, len(X_tr) // 20)
                yeni = X_tr.copy()
                for h in haber_idx:
                    s = yeni[:, h].copy()
                    # zaman bloklarini rastgele yeniden sirala (etiketle iliskisini koparir)
                    parcalar = [s[i:i + blok] for i in range(0, len(s), blok)]
                    rng.shuffle(parcalar)
                    yeni[:, h] = np.concatenate(parcalar)[:len(s)]
                X_tr = yeni

        # Olcekleme YALNIZCA egitimden ogrenilir
        if ayar["model"].get("olcekleme") == "standard":
            sc = StandardScaler().fit(X_tr)
            X_tr = sc.transform(X_tr); X_te = sc.transform(X_te)

        model, kullanilan = model_olustur(ayar, tohum)
        model.fit(X_tr, y_tr)
        proba = model.predict_proba(X_te)
        # sinif eksikse sutunlari hizala
        if proba.shape[1] != 5:
            tam = np.zeros((len(proba), 5))
            for j, c in enumerate(model.classes_):
                tam[:, int(c)] = proba[:, j]
            proba = tam

        # test dilimine ait kapanis fiyatlari (ayni uzunlukta, sira ile hizali)
        kapanis_te = df["close"].iloc[t0:t1].to_numpy(float) if "close" in df.columns else None
        m = metrikler_hesapla(y_te, proba, kapanis_te, ayar)
        m["kat"] = len(kat_metrikleri) + 1
        m["egitim_bar"] = int(e1 - e0); m["test_bar"] = int(t1 - t0)
        kat_metrikleri.append(m)
        tum_y.append(y_te); tum_p.append(proba)
        # POZISYONLAR (df icindeki 0..n-1) - .iloc ile hizali
        tum_idx.append(np.arange(t0, t1, dtype=np.int64))

    y_all = np.concatenate(tum_y); p_all = np.concatenate(tum_p); idx_all = np.concatenate(tum_idx)

    # --- dilimler (idx_all: df icindeki POZISYONLAR)
    olay_mask = dilim_maskesi(df, idx_all, ayar)
    dilimler = {
        "tum": np.ones(len(y_all), dtype=bool),
        "olay_penceresi": olay_mask,
        "olay_disi": ~olay_mask,
    }
    dilim_metrikleri = {}
    kapanis_all = df["close"].to_numpy(float)[idx_all] if "close" in df.columns else None
    for ad_d, mask in dilimler.items():
        if mask.sum() < 10:
            dilim_metrikleri[ad_d] = {"uyari": f"yetersiz satir ({int(mask.sum())})"}
            continue
        mm = metrikler_hesapla(y_all[mask], p_all[mask],
                               kapanis_all[mask] if kapanis_all is not None else None,
                               ayar)
        mm["satir"] = int(mask.sum())
        dilim_metrikleri[ad_d] = mm

    return {
        "deney": ad, "tohum": tohum, "ozellik_sayisi": len(feats), "ozellikler": feats,
        "model": model_olustur(ayar, tohum)[1], "karistir_haber": karistir_haber,
        "katlar": kat_metrikleri, "dilimler": dilim_metrikleri,
        "y": y_all, "p": p_all, "idx": idx_all,
    }


def dilim_maskesi(df: pd.DataFrame, idx: np.ndarray, ayar: dict) -> np.ndarray:
    """
    Olay penceresi dilimi: yuksek onemli olaydan -1sa .. +4sa icindeki barlar.

    idx: test dilimindeki barlarin df ICINDEKI POZISYONLARI (0..len(df)-1).
    Doner: idx ile ayni uzunlukta boolean maske.
    """
    once_dk = float(ayar["dilimler"]["olay_once_saat"]) * 60.0
    sonra_dk = float(ayar["dilimler"]["olay_sonra_saat"]) * 60.0

    kalan = df["takvim_kalan_dk"].to_numpy(float)
    gecen = df["takvim_gecen_dk"].to_numpy(float)
    # olay anindan SONRA: gecen_dk kucukse olay az once oldu
    # olaydan ONCE: kalan_dk kucukse olay yakinda
    yakin = (gecen <= sonra_dk) | (kalan <= once_dk)
    poz = np.asarray(idx, dtype=np.int64)
    return yakin[poz]


# ------------------------------------------------------------------
# Rapor
# ------------------------------------------------------------------
def rapor_yaz(sonuclar: list[dict], ayar: dict, sure_sn: float, hiz_notu: str,
              rastgele_deneyler: tuple[str, ...] = ()) -> None:
    satir = ["# Fayda testi raporu — haber/makro özellikleri", "",
             f"Üretim: {datetime.now():%Y-%m-%d %H:%M} | toplam süre {sure_sn:.1f} sn",
             f"Model: {sonuclar[0]['model'] if sonuclar else '?'} | "
             f"walk-forward {ayar['bolme']['kat_sayisi']} kat | embargo {ayar['bolme']['embargo_bar']} bar",
             f"Kilit: {'AÇIK' if ayar['kilit']['kilidi_ac'] else 'KAPALI'} "
             f"({ayar['kilit']['kilit_baslangici']} sonrası {'dahil' if ayar['kilit']['kilidi_ac'] else 'hariç'})",
             "",
             "Not: A, B, C, D, F, G deneyleri deterministiktir (HistGradientBoosting bu veri "
             "boyutunda random_state'e duyarsız); tek koşu yapılır ve std kolonu \"—\" gösterilir. "
             "E (karıştırma) rastgelelik içerdiği için 5 tohumla koşulur.",
             "", hiz_notu, "", "## Sonuçlar (tüm barlar dilimi)", "",
             "| Deney | Özellik | Makro-F1 (ort±std) | Log-loss (ort±std) | Sim. işlem | Sim. toplam USD |",
             "|---|---|---|---|---|---|"]

    gruplar: dict[str, list[dict]] = {}
    for s in sonuclar:
        gruplar.setdefault(s["deney"], []).append(s)

    def ort_std(degerler: list[float], tek_kosu: bool) -> str:
        if tek_kosu or len(degerler) < 2:
            return f"{np.nanmean(degerler):.4f} ± —"
        return f"{np.nanmean(degerler):.4f} ± {np.nanstd(degerler):.4f}"

    for ad, kosular in gruplar.items():
        tek = (ad not in rastgele_deneyler) or len(kosular) < 2
        f1 = [k["dilimler"]["tum"].get("makro_f1", np.nan) for k in kosular]
        ll = [k["dilimler"]["tum"].get("log_loss", np.nan) for k in kosular]
        isl = [k["dilimler"]["tum"].get("islem", 0) for k in kosular]
        top = [k["dilimler"]["tum"].get("toplam_usd", 0.0) for k in kosular]
        satir.append(f"| {ad} | {kosular[0]['ozellik_sayisi']} | "
                     f"{ort_std(f1, tek)} | "
                     f"{ort_std(ll, tek)} | "
                     f"{int(np.mean(isl))} | {np.mean(top):+.2f} |")

    satir += ["", "## Dilim kırılımı (tüm tohumların ortalaması)", "",
              "| Deney | Dilim | Makro-F1 | Log-loss | Satır |", "|---|---|---|---|---|"]
    for ad, kosular in gruplar.items():
        for dilim in ("tum", "olay_penceresi", "olay_disi"):
            f1 = [k["dilimler"][dilim].get("makro_f1", np.nan) for k in kosular
                  if "makro_f1" in k["dilimler"].get(dilim, {})]
            ll = [k["dilimler"][dilim].get("log_loss", np.nan) for k in kosular
                  if "log_loss" in k["dilimler"].get(dilim, {})]
            nn = [k["dilimler"][dilim].get("satir", 0) for k in kosular]
            if not f1:
                continue
            satir.append(f"| {ad} | {dilim} | {np.nanmean(f1):.4f} | {np.nanmean(ll):.4f} | "
                         f"{int(np.mean(nn))} |")

    satir += ["", "## Blok bootstrap (%95) — D ile karşılaştırma", "",
              "| Karşılaştırma | Makro-F1 farkı | %95 CI | Anlamlı mı |", "|---|---|---|---|"]
    if "D_hepsi" in gruplar:
        base = gruplar["D_hepsi"]
        for ad, kosular in gruplar.items():
            if ad == "D_hepsi":
                continue
            # ayni tohumlarin f1 farklarini barlar uzerinden bootstrap et
            try:
                a = base[0]["y"]; pa = base[0]["p"]; pb = kosular[0]["p"]
                fa = (np.argmax(pa, axis=1) == a).astype(float)
                fb = (np.argmax(pb, axis=1) == a).astype(float)
                lo, hi = blok_bootstrap_ci(fa, fb, ayar, tohum=int(base[0]["tohum"]))
                anlamli = "EVET" if (lo > 0 or hi < 0) else "hayır"
                satir.append(f"| D - {ad} | {fa.mean()-fb.mean():+.4f} | "
                             f"[{lo:+.4f}, {hi:+.4f}] | {anlamli} |")
            except Exception as hata:  # noqa: BLE001
                satir.append(f"| D - {ad} | hata: {hata} | - | - |")
    else:
        satir.append("| (D koşusu bulunamadı) | - | - | - |")

    with open("fayda_raporu.md", "w", encoding="utf-8") as f:
        f.write("\n".join(satir) + "\n")
    print("[rapor] fayda_raporu.md yazildi")


# ------------------------------------------------------------------
# PARALEL IS: modul duzeyinde is fonksiyonu (Windows spawn uyumlu)
#  - Her isci kendi BLAS/OpenMP is parcacigini threadpoolctl ile sinirlar
#    (asiri abonelik olmasin).
#  - Ayar/veri her isceye pickle ile gecilir; global durum YOK.
# ------------------------------------------------------------------
def _is_kos(paket: dict) -> dict:
    ayar = paket["ayar"]
    try:
        from threadpoolctl import threadpool_limits  # noqa: PLC0415
        limit = int(ayar["model"].get("blas_thread_limit", 2))
    except ImportError:
        threadpool_limits = None
        limit = None

    if threadpool_limits is not None and limit:
        with threadpool_limits(limits=limit):
            return deney_kos(paket["ad"], paket["kolonlar"], paket["df"], ayar,
                             paket["bolmeler"], paket["tohum"], paket["karistir"])
    return deney_kos(paket["ad"], paket["kolonlar"], paket["df"], ayar,
                     paket["bolmeler"], paket["tohum"], paket["karistir"])


# ------------------------------------------------------------------
# Ana akis
# ------------------------------------------------------------------
def main(hiz_modu: bool = False) -> int:
    t0 = time.time()
    ayar = ayar_yukle()
    df = veriyi_hazirla(ayar)
    bolmeler_liste = bolmeler(df, ayar)
    tohumlar = ayar["model"]["rastgele_tohumlar"]
    os.makedirs("deneyler", exist_ok=True)

    haber_kolonlari = HABER_TAKVIM + HABER_FRED
    fiyat_kolonlari = [c for c in df.columns if c not in haber_kolonlari
                       and not c.endswith("_eksik") and c != "y"]
    fiyat_kolonlari = [c for c in fiyat_kolonlari if not c.startswith(("takvim_", "fred_"))]

    deneyler = [
        ("A_fiyat", fiyat_kolonlari, False),
        ("B_fiyat_takvim", fiyat_kolonlari + [c for c in HABER_TAKVIM if c in df.columns], False),
        ("C_fiyat_fred", fiyat_kolonlari + [c for c in HABER_FRED if c in df.columns], False),
        ("D_hepsi", fiyat_kolonlari + [c for c in haber_kolonlari if c in df.columns], False),
        ("E_kontrol_karistirilmis", fiyat_kolonlari + [c for c in haber_kolonlari if c in df.columns], True),
        ("F_ablasyon_kalan_dk_yok",
         [c for c in fiyat_kolonlari + [c for c in haber_kolonlari if c in df.columns]
          if c != "takvim_kalan_dk"], False),
        ("G_gecikme_0", fiyat_kolonlari + [c for c in haber_kolonlari if c in df.columns], False),
    ]

    if hiz_modu:
        # HIZ TESTI: kucuk alt ornek, 2 kat, 1 tohum -> tahmini sure
        print("\n=== HIZ TESTI (alt ornek) ===")
        alt = int(ayar["hiz_testi"]["alt_ornek"])
        df_k = df.iloc[-alt:].copy()
        bol_k = bolmeler(df_k, {**ayar, "bolme": {**ayar["bolme"],
                                                  "kat_sayisi": ayar["hiz_testi"]["kat_sayisi"]}})
        th = time.time()
        _ = deney_kos("HIZ_A", fiyat_kolonlari, df_k, ayar, bol_k, tohumlar[0])
        th2 = time.time()
        _ = deney_kos("HIZ_D", fiyat_kolonlari + haber_kolonlari, df_k, ayar, bol_k, tohumlar[0])
        th3 = time.time()
        s1 = th2 - th; s2 = th3 - th2
        n_tam = len(df)
        kat_orani = ayar["bolme"]["kat_sayisi"] / max(1, ayar["hiz_testi"]["kat_sayisi"])
        bar_orani = n_tam / max(1, len(df_k))
        deney_sayisi = len(deneyler) + 2   # G icin 3 varyant
        tahmini = (s1 + s2) / 2 * kat_orani * bar_orani * deney_sayisi
        print(f"[hiz] A: {s1:.2f} sn | D: {s2:.2f} sn | alt ornek {alt} bar, "
              f"{ayar['hiz_testi']['kat_sayisi']} kat, 1 tohum")
        print(f"[hiz] tahmini TAM kosu: ~{tahmini/60:.1f} dk "
              f"({deney_sayisi} deney, deterministik tek tohum + E icin 5 tohum, {n_tam} bar, "
              f"{ayar['bolme']['kat_sayisi']} kat)")
        with open("deneyler/hiz_testi.json", "w", encoding="utf-8") as f:
            json.dump({"A_sn": s1, "D_sn": s2, "alt_ornek": alt, "tam_bar": n_tam,
                       "tahmini_toplam_dk": tahmini / 60}, f, indent=2)
        return 0

    print("\n=== TAM KOSU ===")
    n_jobs = int(ayar["model"].get("n_jobs", 4))
    blas_lim = int(ayar["model"].get("blas_thread_limit", 2))
    # Deterministik deneyler (A,B,C,D,F,G): tek kosu. Rastgelelik iceren E: 5 tohum.
    RASTGELE_DENEYLER = ("E_kontrol_karistirilmis",)
    ilk_tohum = int(tohumlar[0])

    paketler = []
    for ad, kolonlar, karistir in deneyler:
        if ad in RASTGELE_DENEYLER:
            for th in tohumlar:
                paketler.append({"ad": ad, "kolonlar": kolonlar, "df": df, "ayar": ayar,
                                 "bolmeler": bolmeler_liste, "tohum": int(th),
                                 "karistir": karistir})
        else:
            paketler.append({"ad": ad, "kolonlar": kolonlar, "df": df, "ayar": ayar,
                             "bolmeler": bolmeler_liste, "tohum": ilk_tohum,
                             "karistir": karistir})

    # G deneyi: gecikme duyarliligi (0/15/30) — deterministik, tek tohum
    for gecikme in (0, 15, 30):
        df_g = df.copy()
        for c in haber_kolonlari:
            if c in df_g.columns:
                df_g[c] = df_g[c].shift(gecikme // 15).fillna(0.0)
        df_g = df_g.dropna(subset=fiyat_kolonlari)
        paketler.append({"ad": f"G_gecikme_{gecikme}",
                         "kolonlar": fiyat_kolonlari + haber_kolonlari,
                         "df": df_g, "ayar": ayar, "bolmeler": bolmeler_liste,
                         "tohum": ilk_tohum, "karistir": False})

    print(f"[paralel] {len(paketler)} kosu, n_jobs={n_jobs}, BLAS limit={blas_lim}/isci")
    t_par = time.time()
    from joblib import Parallel, delayed  # noqa: PLC0415
    ham = Parallel(n_jobs=n_jobs, backend="loky", verbose=5)(
        delayed(_is_kos)(p) for p in paketler)
    print(f"[paralel] tamamlandi: {time.time()-t_par:.1f} sn")

    sonuclar = []
    for s, p in zip(ham, paketler):
        s["sure_sn"] = None
        ad, tohum = p["ad"], p["tohum"]
        kayit = {k: v for k, v in s.items() if k not in ("y", "p", "idx")}
        kayit["ayar_ozeti"] = {"model": ayar["model"], "bolme": ayar["bolme"],
                               "kilit": ayar["kilit"], "metrikler": ayar["metrikler"]}
        with open(f"deneyler/{ad}_tohum{tohum}.json", "w", encoding="utf-8") as f:
            json.dump(kayit, f, indent=2, ensure_ascii=False, default=str)
        print(f"  {ad} tohum={tohum}: F1={s['dilimler']['tum'].get('makro_f1', float('nan')):.4f}")
        sonuclar.append(s)

    sure = time.time() - t0
    rapor_yaz(sonuclar, ayar, sure, "Paralel kosu (joblib loky).",
              rastgele_deneyler=RASTGELE_DENEYLER)
    print(f"\n[bitis] toplam {sure:.1f} sn")
    return 0


if __name__ == "__main__":
    mod = "--tam" in sys.argv
    sys.exit(main(hiz_modu=not mod))
