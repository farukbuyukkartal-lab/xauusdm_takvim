#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Olay calismasi: ABD makro aciklamalarindan sonra altin (XAUUSDm M15) tepkisi.
Soru: olaydan 1/4/24/48 saat sonra (a) hareket buyuklugu normal zamanlardan farkli mi,
(b) surpriz isareti getiri yonunu ongoruyor mu? KESIFSEL analiz; model egitilmez.
Kilitli son 6 ay (>= KILIT) hicbir hesapta kullanilmaz."""
import os
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

# ===================== AYARLAR =====================
DIZIN = os.environ.get("VERI_DIZINI", os.path.join(os.environ.get("APPDATA", ""), "MetaQuotes", "Terminal", "Common", "Files"))
BARLAR, TAKVIM = "bars_mql5.csv", "calendar_events.csv"
KILIT = pd.Timestamp("2026-04-17")           # bu tarih ve sonrasi OKUNMAZ
UFUKLAR = {"1sa": 4, "4sa": 16, "24sa": 96, "48sa": 192}   # M15 bar sayisi (piyasa acik barlar)
ATR_BAR = 14 * 96                            # 14 gunluk M15 ATR (high-low ortalamasi)
TABAN_N, TABAN_UZAK_SA, BOOT, TOHUM = 1000, 6, 2000, 42
ESLEME_TOLERANS_DK = 30                      # olaydan sonra bu kadar dk icinde bar acilmazsa 'kapali'
# Onceden belirlenmis aileler (veriye bakilmadan secildi). Isaret: +1 = ABD dolari icin olumlu
AILELER = {
    "NFP (Tarim Disi Istihdam)":      (840030016, +1),
    "Cekirdek TUFE (Aylik)":          (840030006, +1),
    "Cekirdek PCE (Aylik)":           (840010001, +1),
    "Perakende Satislar (Aylik)":     (840020010, +1),
    "ISM Uretim PMI":                 (840040001, +1),
    "GSYIH (Ceyreklik)":              (840010007, +1),
}
FOMC_ID = 840050014                          # tahmin (forecast) yok -> yalniz mutlak hareket orani
CIKTI = "olay_calismasi.md"
# ====================================================


def bh(p, q=0.05):
    p = np.asarray(p, float); n = len(p); o = np.argsort(p)
    esik = q * (np.arange(1, n + 1) / n)
    gec = p[o] <= esik
    k = np.max(np.where(gec)[0]) + 1 if gec.any() else 0
    r = np.zeros(n, bool); r[o[:k]] = True
    return r


def veri_oku():
    b = pd.read_csv(os.path.join(DIZIN, BARLAR))
    b["t"] = pd.to_datetime(b["zaman_sunucu"], errors="coerce")
    b = b.dropna(subset=["t"]).sort_values("t")
    b = b[b["t"] < KILIT].reset_index(drop=True)
    c = pd.read_csv(os.path.join(DIZIN, TAKVIM), encoding="cp1254")
    c["t"] = pd.to_datetime(c["olay_zamani_sunucu"], errors="coerce")
    c = c.dropna(subset=["t", "event_id"])
    c = c[(c["ulke_kodu"] == "US") & (c["onem"] == "high") & (c["t"] < KILIT)].copy()
    c["event_id"] = c["event_id"].astype("int64")
    return b, c.sort_values(["t", "event_id"], kind="stable").reset_index(drop=True)


def hazirla(b):
    t = b["t"].to_numpy("datetime64[ns]")
    aralik = (b["high"] - b["low"]).to_numpy()
    atr = pd.Series(aralik).rolling(ATR_BAR).mean().shift(1).to_numpy()   # yalniz ONCEKI barlar
    return t, b["open"].to_numpy(), b["close"].to_numpy(), atr


def getiri(i, k, o, cl, atr):
    j = i + k - 1
    if i < ATR_BAR + 1 or j >= len(o) or not np.isfinite(atr[i]) or atr[i] <= 0:
        return np.nan
    return (cl[j] - o[i]) / (atr[i] * np.sqrt(k))


GECIKMELI = {"4sa→24sa": (16, 96), "4sa→48sa": (16, 192)}   # (baslangic bar, bitis bar) olaydan itibaren


def getiri_aralik(i, bas, bit, o, cl, atr):
    """Ilk tepkiyi (ilk 4 sa) disarida birakan getiri: open[i+bas] -> close[i+bit-1], ATR olay aninda."""
    j, st, k = i + bit - 1, i + bas, bit - bas
    if i < ATR_BAR + 1 or j >= len(o) or not np.isfinite(atr[i]) or atr[i] <= 0:
        return np.nan
    return (cl[j] - o[st]) / (atr[i] * np.sqrt(k))


def surpriz_z(c):
    """actual-forecast, o event_id'nin YALNIZ onceki yayinlarinin std'sine bolunur (min 5)."""
    z = pd.Series(np.nan, index=c.index)
    for _, g in c.groupby("event_id"):
        s = (g["actual"] - g["forecast"]).to_numpy()
        for n, idx in enumerate(g.index):
            gec = s[:n][np.isfinite(s[:n])]
            if np.isfinite(s[n]) and len(gec) >= 5 and gec.std(ddof=1) > 0:
                z[idx] = s[n] / gec.std(ddof=1)
    return z


def olay_tablosu(c, t, o, cl, atr, aileler):
    """Her olay icin bar indeksi, isaretli z ve ufuk getirileri."""
    satirlar = []
    for ad, (eid, isaret) in aileler.items():
        g = c[c["event_id"] == eid]
        for ix, r in g.iterrows():
            i = int(np.searchsorted(t, np.datetime64(r["t"]), side="left"))
            if i >= len(t) or (t[i] - np.datetime64(r["t"])) > np.timedelta64(ESLEME_TOLERANS_DK, "m"):
                continue                                   # piyasa kapaliyken gelen olay
            d = {"aile": ad, "t": r["t"], "i": i, "z": r["z"] * isaret if np.isfinite(r["z"]) else np.nan}
            for u, k in UFUKLAR.items():
                d[u] = getiri(i, k, o, cl, atr)
            satirlar.append(d)
    return pd.DataFrame(satirlar)


def taban_ornek(c_tum, t, o, cl, atr, olay_zamanlari, rng):
    """Olay zamanlariyla ayni (hafta ici, saat:dk) olan, tum yuksek onemli ABD olaylarindan >=6sa uzak noktalar."""
    zt = pd.DatetimeIndex(t)
    anahtar = zt.dayofweek * 10000 + zt.hour * 100 + zt.minute
    ev = np.sort(c_tum["t"].to_numpy("datetime64[ns]"))
    pos = np.searchsorted(ev, t)
    sol = np.where(pos > 0, np.abs(t - ev[np.clip(pos - 1, 0, len(ev) - 1)]), np.timedelta64(10**6, "h"))
    sag = np.where(pos < len(ev), np.abs(ev[np.clip(pos, 0, len(ev) - 1)] - t), np.timedelta64(10**6, "h"))
    uzak = (np.minimum(sol, sag) >= np.timedelta64(TABAN_UZAK_SA, "h")) & (np.arange(len(t)) > ATR_BAR + 1) \
           & (np.arange(len(t)) + max(UFUKLAR.values()) < len(t))
    ok = pd.DataFrame({"anahtar": anahtar, "i": np.arange(len(t))})[uzak]
    havuz = ok.groupby("anahtar")["i"].apply(np.array).to_dict()
    ot = pd.DatetimeIndex(olay_zamanlari)
    ok_anahtar = (ot.dayofweek * 10000 + ot.hour * 100 + ot.minute).to_numpy()
    secilen = []
    for a in rng.choice(ok_anahtar, TABAN_N):
        if a in havuz:
            secilen.append(rng.choice(havuz[a]))
    return {u: np.array([getiri(i, k, o, cl, atr) for i in secilen]) for u, k in UFUKLAR.items()}, np.array(secilen)


def ratio_ci(ev_ret, tb_ret, rng):
    ev = np.abs(ev_ret[np.isfinite(ev_ret)]); tb = np.abs(tb_ret[np.isfinite(tb_ret)])
    if len(ev) < 5 or len(tb) < 50:
        return len(ev), np.nan, np.nan, np.nan
    oran = ev.mean() / tb.mean()
    bs = [rng.choice(ev, len(ev)).mean() / rng.choice(tb, len(tb)).mean() for _ in range(BOOT)]
    return len(ev), oran, *np.percentile(bs, [2.5, 97.5])


def rho_ci(z, r, rng):
    m = np.isfinite(z) & np.isfinite(r); z, r = z[m], r[m]
    if len(z) < 10:
        return len(z), np.nan, np.nan, np.nan, np.nan
    rho, p = spearmanr(z, r)
    bs = []
    for _ in range(BOOT):
        ix = rng.integers(0, len(z), len(z))
        v = spearmanr(z[ix], r[ix])[0]
        if np.isfinite(v):
            bs.append(v)
    return len(z), rho, p, *np.percentile(bs, [2.5, 97.5])


def f(x, n=3, isr=False):
    return "—" if not np.isfinite(x) else (f"{x:+.{n}f}" if isr else f"{x:.{n}f}")


def main():
    rng = np.random.default_rng(TOHUM)
    b, c = veri_oku()
    c["z"] = surpriz_z(c)
    t, o, cl, atr = hazirla(b)
    ol = olay_tablosu(c, t, o, cl, atr, AILELER)
    fomc = olay_tablosu(c, t, o, cl, atr, {"FOMC faiz karari": (FOMC_ID, +1)})
    tum_aile = pd.concat([ol, fomc])
    tb, tb_idx = taban_ornek(c, t, o, cl, atr, tum_aile["t"], rng)

    md = ["# Olay çalışması (düzeltilmiş) — havuzlu ve tekil aileler", "",
          f"**Dönem:** {b['t'].min():%Y-%m-%d} → {b['t'].max():%Y-%m-%d} (kilitli son 6 ay HARİÇ, < {KILIT:%Y-%m-%d}) | "
          f"**Taban:** {TABAN_N} nokta, olay zamanlarıyla aynı hafta içi/saat, tüm yüksek önemli ABD olaylarından ≥ {TABAN_UZAK_SA} sa uzak",
          f"**Taban mutlak ortalama (normalize):** " + ", ".join(f"{u}={np.nanmean(np.abs(v)):.3f}" for u, v in tb.items()), "",
          "Normalizasyon: getiri / (ATR_M15 × √bar_sayısı), ATR yalnızca olaydan önceki 14 günden. "
          "Getiri, olay anında açılan barın açılışından ufuk sonundaki kapanışa. Piyasa kapalı olaylar hariç.", "",
          "## Aileler (event_id)", ""]
    for ad, (eid, s) in AILELER.items():
        g = ol[ol.aile == ad]
        md.append(f"- {ad}: event_id={eid}, eşleşen olay={len(g)}, z hesaplanabilen={int(g['z'].notna().sum())}")
    md.append(f"- FOMC faiz kararı: event_id={FOMC_ID}, eşleşen olay={len(fomc)} (tahmin yok → yalnız büyüklük oranı)")

    # ---- Havuzlu
    md += ["", "## Havuzlu analiz (6 aile birlikte; z işareti: ABD doları için olumlu = +)", "",
           "| Ufuk | n | Oran (mutlak) | Oran %95 CI | n(ρ) | Spearman ρ | ρ %95 CI | p | BH anlamlı |", "|---|---|---|---|---|---|---|---|---|"]
    havuz_rho = {}
    for u in UFUKLAR:
        n, oran, lo, hi = ratio_ci(ol[u].to_numpy(), tb[u], rng)
        nr, rho, p, rl, rh = rho_ci(ol["z"].to_numpy(), ol[u].to_numpy(), rng)
        havuz_rho[u] = (n, oran, lo, hi, nr, rho, p, rl, rh)
    bh_h = bh([v[6] if np.isfinite(v[6]) else 1.0 for v in havuz_rho.values()])
    for (u, v), s in zip(havuz_rho.items(), bh_h):
        md.append(f"| {u} | {v[0]} | {f(v[1],2)} | [{f(v[2],2)}, {f(v[3],2)}] | {v[4]} | {f(v[5],3,True)} | "
                  f"[{f(v[7],3,True)}, {f(v[8],3,True)}] | {f(v[6],3)} | {'EVET' if s else 'hayır'} |")

    # ---- Tekil
    md += ["", "## Tekil aileler (KEŞİFSEL; ρ için 24 testin BH düzeltmesi)", "",
           "| Aile | Ufuk | n | Oran | Oran %95 CI | n(ρ) | ρ | ρ %95 CI | p | BH(24) |", "|---|---|---|---|---|---|---|---|---|---|"]
    satir = []
    for ad in AILELER:
        g = ol[ol.aile == ad]
        for u in UFUKLAR:
            n, oran, lo, hi = ratio_ci(g[u].to_numpy(), tb[u], rng)
            nr, rho, p, rl, rh = rho_ci(g["z"].to_numpy(), g[u].to_numpy(), rng)
            satir.append([ad, u, n, oran, lo, hi, nr, rho, rl, rh, p])
    bh24 = bh([s[10] if np.isfinite(s[10]) else 1.0 for s in satir])
    for s, a in zip(satir, bh24):
        flag = " (yetersiz örnek)" if s[2] < 20 else ""
        md.append(f"| {s[0]} | {s[1]} | {s[2]}{flag} | {f(s[3],2)} | [{f(s[4],2)}, {f(s[5],2)}] | {s[6]} | "
                  f"{f(s[7],3,True)} | [{f(s[8],3,True)}, {f(s[9],3,True)}] | {f(s[10],3)} | {'EVET' if a else 'hayır'} |")

    md += ["", "## FOMC faiz kararı (yalnız hareket büyüklüğü; tahmin verisi yok)", "",
           "| Ufuk | n | Oran | %95 CI |", "|---|---|---|---|"]
    for u in UFUKLAR:
        n, oran, lo, hi = ratio_ci(fomc[u].to_numpy(), tb[u], rng)
        md.append(f"| {u} | {n} | {f(oran,2)} | [{f(lo,2)}, {f(hi,2)}] |")

    # ---- Gecikmeli etki (ilk 4 saatlik tepki DISARIDA) -- sonuclari gordukten sonra eklendi, KESIFSEL
    md += ["", "## Gecikmeli etki: ilk 4 saatlik tepki dışarıda bırakıldı (sonradan eklendi, KEŞİFSEL)", "",
           "Soru: ilk tepkiden SONRAKI hareket (olay+4sa → +24sa / +48sa) normalden büyük mü ve sürpriz işaretiyle ilişkili mi? "
           "(24sa/48sa oranı, ilk anlık sıçramanın kalıcı olmasından da yükselebilir; bu bölüm onu ayırır.)", "",
           "| Kapsam | Pencere | n | Oran | Oran %95 CI | n(ρ) | ρ | ρ %95 CI | p | BH |", "|---|---|---|---|---|---|---|---|---|---|"]
    kayit = []
    for kapsam in ["HAVUZLU"] + list(AILELER):
        g = ol if kapsam == "HAVUZLU" else ol[ol.aile == kapsam]
        for pad, (bas, bit) in GECIKMELI.items():
            er = np.array([getiri_aralik(int(i), bas, bit, o, cl, atr) for i in g["i"]])
            tr = np.array([getiri_aralik(int(i), bas, bit, o, cl, atr) for i in tb_idx])
            n, oran, lo, hi = ratio_ci(er, tr, rng)
            nr, rho, p, rl, rh = rho_ci(g["z"].to_numpy(), er, rng)
            kayit.append([kapsam, pad, n, oran, lo, hi, nr, rho, rl, rh, p])
    bh_g = bh([k[10] if np.isfinite(k[10]) else 1.0 for k in kayit])
    for k, a in zip(kayit, bh_g):
        md.append(f"| {k[0]} | {k[1]} | {k[2]} | {f(k[3],2)} | [{f(k[4],2)}, {f(k[5],2)}] | {k[6]} | "
                  f"{f(k[7],3,True)} | [{f(k[8],3,True)}, {f(k[9],3,True)}] | {f(k[10],3)} | {'EVET' if a else 'hayır'} |")
    md.append("")
    md.append(f"BH düzeltmesi bu bölümdeki {len(kayit)} testin tamamı üzerinden.")

    md += ["", "## Sınırlamalar", "",
           "1. 24sa/48sa ufuklarda aynı pencerede başka yüksek önemli olaylar da fiyatı etkiler (karıştırıcı etki); "
           "taban noktaları bu karışıklığı kısmen taşıdığı için oran bunu kısmen dengeler, tamamen değil.",
           "2. Keşifsel analiz: aile seçimi ve işaret eşlemesi veriye bakmadan önceden belirlendi, ama test sayısı yine de çoklu; "
           "BH düzeltmesi yalnızca bu tablodaki testleri kapsar.",
           "3. Aile başına yaklaşık 45-50 olay: yalnızca büyük etkiler ayırt edilebilir (ρ için yaklaşık |ρ| > 0,3).",
           "4. Aynı gün/saat yayınlanan olaylar (ör. GSYİH ve PCE) havuzda bağımsız sayıldı; güven aralıkları hafif iyimser olabilir.",
           "5. ATR high-low ortalamasıdır (hafta sonu boşlukları hariç).", "",
           "**İşaretleme:** sayılar [GERÇEK VERİ] (gerçek MT5 bar ve takvim). Bootstrap/taban örneklemi rastgelelik içerir, tohum=42. "
           "[ÇALIŞTIRILMADI] model eğitimi; kilitli dönem okunmadı."]
    with open(CIKTI, "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
