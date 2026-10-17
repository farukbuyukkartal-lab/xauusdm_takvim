# Adım 4 — Fayda testi: SÜRE RAPORU (onay bekleniyor)

**Tarih:** 2026-10-17 | **Makine:** i5 sınıfı, 12 mantıksal çekirdek, GPU yok

## Ölçülen süreler `[GERÇEK VERİ]`

| Ölçüm | Kapsam | Süre |
|---|---|---|
| Hız testi (alt örnek 15.000 bar, 2 kat, 1 tohum) | deney A | 5,6 sn |
| Hız testi (alt örnek 15.000 bar, 2 kat, 1 tohum) | deney D | 6,7 sn |
| **Gerçek ölçüm** — deney A, 6 kat, 87.958 bar, 1 tohum | tam | **32,2 sn** |
| **Gerçek ölçüm** — deney D, 6 kat, 87.958 bar, 1 tohum | tam | **41,3 sn** |

Alt örnekle yapılan tahmin (81 dk) **yanıltıcıydı**: küçük veride sabit maliyetler (import, kıvılcım) baskın çıkıyor. Gerçek ölçüm 1 kat üzerinden yapıldı ve ölçeklendi.

## Tahmini toplam süre

| | Deney sayısı | Tohum | Koşu | Ort. sn/koşu | Toplam |
|---|---|---|---|---|---|
| Tüm deneyler (A–G) | 7 + G'nin 3 varyantı = 9 | 5 | 45 | ~37 | **~28 dakika** |
| Yalnız A–D (4 deney) | 4 | 5 | 20 | ~37 | ~12 dakika |

**Önerilen:** tam koşu **~28 dakika**. Onay verirsen başlatıyorum.

## Notlar

- Model: **sklearn HistGradientBoostingClassifier** (lightgbm bu makinede **kurulu değil** — `[ÇALIŞTIRILMADI]`).
- Veri: 100.000 bar → kilit nedeniyle **87.958 bar** (2026-04-17 sonrası çıkarıldı, `kilit.kilidi_ac: false`).
- Etiket dağılımı: HOLD=1176, BUY=8570, SELL=9627, CLOSE_LONG=33552, CLOSE_SHORT=35033.
- **İlk gözlem (tek tohum, 6 kat, `[GERÇEK VERİ]`):**
  - A (yalnız fiyat): makro-F1 **0,5205**, log-loss 0,5300, 9.148 simülasyon işlemi
  - D (fiyat + hepsi): makro-F1 **0,5364**, log-loss 0,5938, 11.486 işlem
  - → Haber özellikleri makro-F1'i **+0,016** artırdı ama log-loss **kötüleşti** (0,5300 → 0,5938). Tek tohuma bakarak karar verilmez; 5 tohum + bootstrap CI gerekli.

## Onay gerekiyor

Tam koşuyu (~28 dk) başlatmamı onaylıyor musun? İstersen yalnız A–D (~12 dk) ile başlayıp E/F/G'yi sonra çalıştırabilirim.
