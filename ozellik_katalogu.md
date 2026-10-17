# Özellik kataloğu — haber/makro özellikleri

Tüm zamanlar **sunucu saati**. Bir barın özellikleri yalnızca o bar **kapandıktan sonra** bilinen veriyle hesaplanır (bilgi zamanı = bar açılışı + bar süresi).

| Özellik | Açıklama | Parametreler |
|---|---|---|
| `takvim_kalan_dk` | Bir sonraki yüksek önemli olaya kalan dakika (üst sınırla kırpılır) | ulke_kodu=`US`, onem_esigi=`high`, event_id_filtresi=`[]`, ust_sinir_dk=`1440` |
| `takvim_gecen_dk` | Son yüksek önemli olaydan geçen dakika | ust_sinir_dk=`1440` |
| `takvim_pencere` | Olay penceresi bayrağı: olaydan -N/+M dk içinde mi | once_dk=`15`, sonra_dk=`15` |
| `takvim_surpriz_z` | Son olayın sürprizi (actual-forecast), aynı event_id'nin **yalnızca önceki** yayınlarının std'sine bölünmüş z-skor | min_gecmis=`5` |
| `takvim_surpriz_z_sonumlu` | Sürprizin sönümlenmesi: z × exp(-geçen_dk / yarılanma) | yarilanma_dk=`240` |
| `takvim_hafta_sonu` | Hafta sonu bayrağı (Cmt/Paz) | — |
| `takvim_piyasa_kapali` | Piyasa kapalı bayrağı (hafta sonu veya barlar arası boşluk) | gun_sonu_bosluk_dk=`0` |
| `fred_dfii10_degisim` | FRED `DFII10` (degisim) — as-of, geriye bakan | gecikme_saat=`0` |
| `fred_t10yie_degisim` | FRED `T10YIE` (degisim) — as-of, geriye bakan | gecikme_saat=`0` |
| `fred_dgs10_dgs2_fark` | FRED `DGS10−DGS2` (fark) — as-of, geriye bakan | gecikme_saat=`0` |
| `fred_vix_seviye` | FRED `VIXCLS` (seviye) — as-of, geriye bakan | gecikme_saat=`0` |
| `fred_vix_degisim` | FRED `VIXCLS` (degisim) — as-of, geriye bakan | gecikme_saat=`0` |

## Sızıntı kuralları

1. Bar [t, t+süre) aralığını kapsar; bilgi zamanı = t+süre.
2. Takvim actual/forecast değerleri yayın anında bilinir kabul edilir.
3. Sürpriz z-skoru **expanding** ve yalnızca önceki yayınlarla hesaplanır.
4. FRED satırları `kullanilabilir_tarih + gecikme_saat` anından itibaren bilinir; birleştirme `merge_asof(direction='backward')`.
5. `forecast` boşsa sürpriz **NaN** kalır; doldurma yapılmaz.

Üretilen özellik sayısı: **12**, satır: **100000**
