# Fayda testi raporu — haber/makro özellikleri

Üretim: 2026-10-17 20:43 | toplam süre 286.1 sn
Model: sklearn_hist | walk-forward 6 kat | embargo 32 bar
Kilit: KAPALI (2026-04-17 sonrası hariç)

Not: A, B, C, D, F, G deneyleri deterministiktir (HistGradientBoosting bu veri boyutunda random_state'e duyarsız); tek koşu yapılır ve std kolonu "—" gösterilir. E (karıştırma) rastgelelik içerdiği için 5 tohumla koşulur.

Paralel kosu (joblib loky).

## Sonuçlar (tüm barlar dilimi)

| Deney | Özellik | Makro-F1 (ort±std) | Log-loss (ort±std) | Sim. işlem | Sim. toplam USD |
|---|---|---|---|---|---|
| A_fiyat | 24 | 0.5140 ± — | 0.4312 ± — | 6229 | -4320.27 |
| B_fiyat_takvim | 31 | 0.5199 ± — | 0.4352 ± — | 7962 | -14707.26 |
| C_fiyat_fred | 29 | 0.5202 ± — | 0.4459 ± — | 8148 | -7587.08 |
| D_hepsi | 36 | 0.5146 ± — | 0.4490 ± — | 9116 | -17023.62 |
| E_kontrol_karistirilmis | 36 | 0.5003 ± 0.0095 | 0.4524 ± 0.0059 | 8574 | -19185.29 |
| F_ablasyon_kalan_dk_yok | 35 | 0.5214 ± — | 0.4501 ± — | 9017 | -14136.11 |
| G_gecikme_0 | 36 | 0.5146 ± — | 0.4490 ± — | 9116 | -17023.62 |
| G_gecikme_15 | 36 | 0.5182 ± — | 0.4491 ± — | 9057 | -13915.04 |
| G_gecikme_30 | 36 | 0.5192 ± — | 0.4489 ± — | 9038 | -14822.45 |

## Dilim kırılımı (tüm tohumların ortalaması)

| Deney | Dilim | Makro-F1 | Log-loss | Satır |
|---|---|---|---|---|
| A_fiyat | tum | 0.5140 | 0.4312 | 52770 |
| A_fiyat | olay_penceresi | 0.5182 | 0.4417 | 10267 |
| A_fiyat | olay_disi | 0.5126 | 0.4286 | 42503 |
| B_fiyat_takvim | tum | 0.5199 | 0.4352 | 52770 |
| B_fiyat_takvim | olay_penceresi | 0.5200 | 0.4482 | 10267 |
| B_fiyat_takvim | olay_disi | 0.5194 | 0.4321 | 42503 |
| C_fiyat_fred | tum | 0.5202 | 0.4459 | 52770 |
| C_fiyat_fred | olay_penceresi | 0.5247 | 0.4568 | 10267 |
| C_fiyat_fred | olay_disi | 0.5187 | 0.4433 | 42503 |
| D_hepsi | tum | 0.5146 | 0.4490 | 52770 |
| D_hepsi | olay_penceresi | 0.5286 | 0.4622 | 10267 |
| D_hepsi | olay_disi | 0.5103 | 0.4459 | 42503 |
| E_kontrol_karistirilmis | tum | 0.5003 | 0.4524 | 52770 |
| E_kontrol_karistirilmis | olay_penceresi | 0.4994 | 0.4642 | 10267 |
| E_kontrol_karistirilmis | olay_disi | 0.5003 | 0.4495 | 42503 |
| F_ablasyon_kalan_dk_yok | tum | 0.5214 | 0.4501 | 52770 |
| F_ablasyon_kalan_dk_yok | olay_penceresi | 0.5295 | 0.4648 | 10267 |
| F_ablasyon_kalan_dk_yok | olay_disi | 0.5189 | 0.4465 | 42503 |
| G_gecikme_0 | tum | 0.5146 | 0.4490 | 52770 |
| G_gecikme_0 | olay_penceresi | 0.5286 | 0.4622 | 10267 |
| G_gecikme_0 | olay_disi | 0.5103 | 0.4459 | 42503 |
| G_gecikme_15 | tum | 0.5182 | 0.4491 | 52770 |
| G_gecikme_15 | olay_penceresi | 0.5284 | 0.4598 | 10267 |
| G_gecikme_15 | olay_disi | 0.5150 | 0.4465 | 42503 |
| G_gecikme_30 | tum | 0.5192 | 0.4489 | 52770 |
| G_gecikme_30 | olay_penceresi | 0.5255 | 0.4579 | 10267 |
| G_gecikme_30 | olay_disi | 0.5171 | 0.4467 | 42503 |

## Blok bootstrap (%95) — D ile karşılaştırma

| Karşılaştırma | Makro-F1 farkı | %95 CI | Anlamlı mı |
|---|---|---|---|
| D - A_fiyat | -0.0095 | [-0.0154, -0.0035] | EVET |
| D - B_fiyat_takvim | -0.0073 | [-0.0115, -0.0026] | EVET |
| D - C_fiyat_fred | -0.0046 | [-0.0092, +0.0001] | hayır |
| D - E_kontrol_karistirilmis | +0.0001 | [-0.0057, +0.0054] | hayır |
| D - F_ablasyon_kalan_dk_yok | -0.0020 | [-0.0041, -0.0001] | EVET |
| D - G_gecikme_0 | +0.0000 | [+0.0000, +0.0000] | hayır |
| D - G_gecikme_15 | -0.0015 | [-0.0035, +0.0003] | hayır |
| D - G_gecikme_30 | -0.0016 | [-0.0039, +0.0007] | hayır |
