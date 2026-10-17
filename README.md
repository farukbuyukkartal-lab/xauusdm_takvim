# XAUUSDm: takvim ve makro veriyle altın fiyat modeli — sızıntısız veri hattı ve dürüst test

> **Kısaca (EN):** A leakage-checked pipeline that aligns the MT5 economic calendar and FRED macro series with XAUUSDm M15 bars, plus two honest tests. (1) Calendar/macro features did **not** improve a price-based classifier. (2) An event study shows gold volatility is about 2× normal in the first hours after major US releases, with no reliable delayed directional effect. Research code, not trading advice.

## Ana bulgular

1. **Haber/makro özellikleri fiyat tabanlı modele fayda sağlamadı.** Takvim ve FRED özellikleri eklenince makro-F1 değişmedi, log-loss kötüleşti. Taban model dahil, basit maliyetli simülasyon negatif.
2. **Önemli ABD açıklamalarından sonra oynaklık belirgin biçimde artıyor.** İlk saatte ~2,2×, 4 saatte ~1,8× (normal zamanlara göre). Bu, tahmin gerektirmeyen ve işe yarayabilecek bir risk bilgisi.
3. **Anlık yön etkisi gerçek, gecikmeli yön etkisi bulunamadı.** ABD doları için olumlu sürpriz ilk saatte altını düşürüyor. Etki 4 saatte kayboluyor; 24-48 saatte havuzlu analizde yön etkisi yok.
4. **Keşifsel ipucu (doğrulanmamış):** GSYİH sürprizinin ilk saatteki etkisi 1-2 gün içinde tersine dönüyor gibi görünüyor. Karıştırıcı etken var (aşağıda).

Bu bulgular **yalnızca bu veri, sembol ve tasarım için** geçerlidir; "haber hiç işe yaramaz" iddiası değildir.

## Veri

| Veri | Kaynak | Kapsam |
|---|---|---|
| XAUUSDm M15 | MT5 (`BarExport.mq5`) | 100.000 bar, 2022-07-25 → 2026-10-16 |
| Ekonomik takvim | MT5 yerleşik takvimi (`CalendarExport.mq5`) | 62.065 olay, 23 ülke, tüm önem seviyeleri |
| Makro seriler | FRED API (`fred_indir.py`) | DFII10, DGS10, DGS2, T10YIE, VIXCLS, günlük |

- **Veri dosyaları (CSV) depoda yok.** Broker verisi yeniden dağıtılmıyor; aşağıdaki adımlarla kendi terminalinden üretilir.
- **Kilitli test dönemi:** 2026-04-17 ve sonrası hiçbir testte okunmaz (`fayda_ayar.yaml`).
- **Zaman:** Sunucu saati sabit UTC+0 olarak doğrulandı (`CalendarExport` günlüğü: kayma +0 sn; NFP 12:30/13:30 örüntüsü ABD yaz saatini izliyor; Python ve MQL5 barları 100.000/100.000 birebir aynı). Tüm hizalama sunucu saatiyle yapılır.

## Sonuçlar

### 1) Fayda testi (`fayda_testi.py`, `fayda_raporu.md`)

HistGradientBoosting, 6 katlı genişleyen pencereli walk-forward, 32 bar embargo, son 6 ay kilitli. Tüm barlar dilimi:

| Deney | Özellik sayısı | Makro-F1 | Log-loss | Sim. işlem | Sim. toplam (USD) |
|---|---|---|---|---|---|
| A: yalnız fiyat | 24 | 0,5140 | 0,4312 | 6.229 | −4.320 |
| B: + takvim | 31 | 0,5199 | 0,4352 | 7.962 | −14.707 |
| C: + FRED | 29 | 0,5202 | 0,4459 | 8.148 | −7.587 |
| D: + hepsi | 36 | 0,5146 | 0,4490 | 9.116 | −17.024 |
| E: karıştırılmış haber (kontrol) | 36 | 0,5003 ± 0,0095 | 0,4524 | 8.574 | −19.185 |

Yorum:

- Haberli modeller (B, C, D) taban modelden tutarlı bir kazanç göstermedi: makro-F1 farkları küçük ve karışık, log-loss her eklemeyle kötüleşiyor, simülasyon her durumda negatif.
- Karıştırılmış kontrol (E) daha düşük çıktı; bu, gerçek özelliklerin gürültüden hafifçe farklı olduğunu düşündürür ama taban modele göre pratik fayda yaratmaz.
- `takvim_kalan_dk` (sonraki olaya kalan süre, doğası gereği ileriye bakar) çıkarılınca sonuç iyileşti; yani bu özelliğin içinde gizli bir sızıntı avantajı yok.
- **Bilinen sorun:** Rapordaki blok bootstrap güven aralıkları, tablo ortalamalarıyla tutarsız (ör. D−A ortalama farkı ≈ +0,001 iken bootstrap −0,0095 veriyor). Bu yüzden **bu çalışmada anlamlılık iddiası yapılmıyor**; bootstrap kodu yeniden gözden geçirilmeli.
- Ağaç modeli bu veri boyutunda tohumdan bağımsız olduğu için çoklu tohum yalnızca E (rastgele karıştırma) için anlamlı. Tek bir model ailesi denendi.

### 2) Olay çalışması (`olay_calismasi.py`, `olay_calismasi.md`)

Altı ABD açıklama ailesi (NFP, Çekirdek TÜFE, Çekirdek PCE, Perakende Satışlar, ISM Üretim PMI, GSYİH; veriye bakmadan önceden seçildi), n=254 olay. Getiri, olay anındaki barın açılışından ufuk sonundaki kapanışa, olay öncesi 14 günlük ATR ile normalize edilir. Taban: aynı hafta içi/saatte, olaylardan ≥6 saat uzak 1.000 rastgele nokta. Sürpriz z-skoru "ABD doları için olumlu = +".

| Ufuk | Hareket oranı (olay/taban) | %95 CI | Spearman ρ (sürpriz ↔ getiri) | %95 CI |
|---|---|---|---|---|
| 1 saat | 2,22 | [1,91; 2,53] | −0,237 | [−0,369; −0,099] |
| 4 saat | 1,83 | [1,60; 2,07] | −0,064 | [−0,196; +0,071] |
| 24 saat | 1,37 | [1,21; 1,56] | +0,004 | [−0,143; +0,141] |
| 48 saat | 1,33 | [1,19; 1,49] | +0,056 | [−0,087; +0,195] |

- 42 ρ testine Benjamini-Hochberg uygulandığında anlamlı kalan iki testten biri havuzlu 1 saatlik etkidir.
- **24-48 saatteki yüksek oran** büyük ölçüde ilk sıçramanın kalıcı olmasından geliyor: ilk 4 saat dışarıda bırakılınca 4→24 saatte oran 1,11 [0,98; 1,24], 4→48 saatte 1,21 [1,08; 1,34]; yönle ilişki anlamsız (ρ +0,07 ve +0,11).
- FOMC faiz kararı (tahmin verisi yok, yalnız büyüklük): oran 1 saatte 3,3×, 4 saatte 2,8×, 24 saatte 1,7×.
- **GSYİH ipucu:** 4→48 saatte ρ = +0,53 (n=36, p=0,001; 42 testin düzeltmesinden sonra da anlamlı; iki yarıda da pozitif). **Ancak** 36 olayın 32'sinde sonraki 48 saatte Çekirdek PCE açıklaması var, etki ayrıştırılamıyor; ayrıca aile sonuçlar görüldükten sonra incelendi. Hipotez olarak kayıtlı; yeni açıklamalarla ileriye dönük test edilmeli.

## Depo içeriği

```
BarExport.mq5            MT5 script: M15 barlarını CSV'ye yazar
CalendarExport.mq5       MT5 script: ekonomik takvimi CSV'ye yazar
kalite_kontrol.py        Takvim CSV kalite kontrolü, olay→bar eşleme sınıflandırması
fred_indir.py            FRED serilerini indirir (anahtar: FRED_API_KEY ortam değişkeni)
haber_ozellikleri.py     12 sızıntısız özellik üretir + kesme testi (haber_ayar.yaml)
ozellik_katalogu.md      Özellik listesi ve sızıntı kuralları
fayda_testi.py           Walk-forward fayda testi (fayda_ayar.yaml)
fayda_raporu.md          Fayda testi sonuçları
olay_calismasi.py        Olay çalışması
olay_calismasi.md        Olay çalışması sonuçları
araclar/zaman_haritasi.py   MQL5 ve Python bar zamanlarını karşılaştıran ölçüm aracı
```

## Çalıştırma

Windows, MetaTrader 5 terminali (açık ve giriş yapılmış), Python 3.12. Başlıca paketler: pandas, numpy, scipy, scikit-learn, pyyaml, joblib, threadpoolctl, MetaTrader5.

1. `BarExport.mq5` ve `CalendarExport.mq5` dosyalarını `MQL5\Scripts` klasörüne koy, MetaEditor'da derle (F7), bir XAUUSDm grafiğine sürükleyip çalıştır (Strategy Tester'da değil). Çıktılar `%APPDATA%\MetaQuotes\Terminal\Common\Files\` altına yazılır; Experts sekmesinde satır sayıları görünür.
2. `python kalite_kontrol.py` (isteğe bağlı: `python araclar/zaman_haritasi.py`).
3. FRED için ücretsiz API anahtarı al, ortam değişkenine ata (`setx FRED_API_KEY "..."`, terminali yeniden aç), sonra `python fred_indir.py`.
4. `python haber_ozellikleri.py` (çıktının sonunda kesme testi sonucunu oku).
5. `python olay_calismasi.py` (veri klasörü varsayılan olarak MT5 ortak klasörüdür; farklıysa `VERI_DIZINI` ortam değişkenini ayarla).
6. `fayda_testi.py` kendi fiyat özellik ve etiket kodunu ister: `features.py` ve `labeling.py` dosyalarını `model_kodu/` klasörüne koy (`fayda_ayar.yaml` → `model_kodu_klasoru`). Bu dosyalar depoda **yok**; diğer adımlar onlarsız çalışır.

## Tasarım kararları ve çıkarılan dersler

- **Sızıntı önce:** Bar [t, t+15dk) aralığını kapsar, bilgi zamanı bar kapanışıdır. Sürpriz z-skoru yalnızca önceki yayınlarla (expanding) hesaplanır. FRED değerleri bir sonraki iş günü kullanılabilir sayılır.
- **Kesme testi** geliştirme sırasında üç gerçek hatayı yakaladı (sıralama bozulması, kararsız sıralama, yanlış taraf hariç tutma).
- **Zaman dilimi varsayılmadı, ölçüldü.** İlk varsayımlardan biri (tek sabit kaymayla UTC türetmek) yaz saati geçişlerinde yanlış olacaktı.
- **Terminal dili Türkçe** olduğu için olay adlarıyla filtreleme kırılgan; filtreler `event_id` ve ülke koduyla yapılır.
- `HistGradientBoostingClassifier`'da `early_stopping` varsayılanı zaman serisinde rastgele doğrulama kesiti kullanır (sızıntılı); kapatıldı, düzenleme güçlendirildi.

## Sınırlamalar

- Tek sembol, tek broker verisi (XAUUSDm), ~4 yıl, aile başına yaklaşık 45-50 olay: yalnızca büyük etkiler ayırt edilebilir.
- Fayda testinde tek model ailesi (ağaç tabanlı); LSTM ile teyit yapılmadı. Bootstrap güven aralıkları yukarıda belirtilen tutarsızlık nedeniyle güvenilmemeli.
- Olay çalışması keşifseldir; 24-48 saatlik pencerelerde aynı hafta içindeki başka açıklamalar karıştırıcıdır.
- Simülasyonlar basittir; gerçek işlem koşullarını (kayma, değişken spread, swap) tam yansıtmaz.
- Canlıda MT5 takvimi gerçekleşen değeri açıklamadan biraz sonra gösterebilir; geriye dönük testteki "aynı dakikada bilinir" varsayımı biraz iyimserdir.

## Sorumluluk reddi

Bu depo araştırma ve eğitim amaçlıdır. **Yatırım tavsiyesi değildir** ve herhangi bir kârlılık iddiası içermez. Forex ve türev ürün işlemlerinde sermayenin tamamı kaybedilebilir. Kod, yapay zekâ yardımıyla yazılmış ve gözden geçirilmiştir.
