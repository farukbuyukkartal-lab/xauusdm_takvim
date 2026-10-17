# Olay çalışması (düzeltilmiş) — havuzlu ve tekil aileler

**Dönem:** 2022-07-25 → 2026-04-16 (kilitli son 6 ay HARİÇ, < 2026-04-17) | **Taban:** 1000 nokta, olay zamanlarıyla aynı hafta içi/saat, tüm yüksek önemli ABD olaylarından ≥ 6 sa uzak
**Taban mutlak ortalama (normalize):** 1sa=0.638, 4sa=0.633, 24sa=0.522, 48sa=0.543

Normalizasyon: getiri / (ATR_M15 × √bar_sayısı), ATR yalnızca olaydan önceki 14 günden. Getiri, olay anında açılan barın açılışından ufuk sonundaki kapanışa. Piyasa kapalı olaylar hariç.

## Aileler (event_id)

- NFP (Tarim Disi Istihdam): event_id=840030016, eşleşen olay=42, z hesaplanabilen=38
- Cekirdek TUFE (Aylik): event_id=840030006, eşleşen olay=43, z hesaplanabilen=37
- Cekirdek PCE (Aylik): event_id=840010001, eşleşen olay=43, z hesaplanabilen=35
- Perakende Satislar (Aylik): event_id=840020010, eşleşen olay=44, z hesaplanabilen=40
- ISM Uretim PMI: event_id=840040001, eşleşen olay=45, z hesaplanabilen=39
- GSYIH (Ceyreklik): event_id=840010007, eşleşen olay=42, z hesaplanabilen=36
- FOMC faiz kararı: event_id=840050014, eşleşen olay=30 (tahmin yok → yalnız büyüklük oranı)

## Havuzlu analiz (6 aile birlikte; z işareti: ABD doları için olumlu = +)

| Ufuk | n | Oran (mutlak) | Oran %95 CI | n(ρ) | Spearman ρ | ρ %95 CI | p | BH anlamlı |
|---|---|---|---|---|---|---|---|---|
| 1sa | 254 | 2.22 | [1.91, 2.53] | 225 | -0.237 | [-0.369, -0.099] | 0.000 | EVET |
| 4sa | 254 | 1.83 | [1.60, 2.07] | 225 | -0.064 | [-0.196, +0.071] | 0.338 | hayır |
| 24sa | 254 | 1.37 | [1.21, 1.56] | 225 | +0.004 | [-0.143, +0.141] | 0.956 | hayır |
| 48sa | 254 | 1.33 | [1.19, 1.49] | 225 | +0.056 | [-0.087, +0.195] | 0.405 | hayır |

## Tekil aileler (KEŞİFSEL; ρ için 24 testin BH düzeltmesi)

| Aile | Ufuk | n | Oran | Oran %95 CI | n(ρ) | ρ | ρ %95 CI | p | BH(24) |
|---|---|---|---|---|---|---|---|---|---|
| NFP (Tarim Disi Istihdam) | 1sa | 41 | 3.07 | [2.27, 4.00] | 38 | -0.303 | [-0.602, +0.051] | 0.064 | hayır |
| NFP (Tarim Disi Istihdam) | 4sa | 41 | 2.56 | [1.94, 3.18] | 38 | -0.131 | [-0.470, +0.230] | 0.434 | hayır |
| NFP (Tarim Disi Istihdam) | 24sa | 41 | 1.89 | [1.45, 2.38] | 38 | -0.223 | [-0.558, +0.133] | 0.178 | hayır |
| NFP (Tarim Disi Istihdam) | 48sa | 41 | 1.53 | [1.16, 1.90] | 38 | -0.179 | [-0.524, +0.193] | 0.283 | hayır |
| Cekirdek TUFE (Aylik) | 1sa | 42 | 3.47 | [2.50, 4.50] | 37 | -0.361 | [-0.629, -0.038] | 0.028 | hayır |
| Cekirdek TUFE (Aylik) | 4sa | 42 | 2.32 | [1.79, 2.94] | 37 | -0.318 | [-0.604, +0.037] | 0.055 | hayır |
| Cekirdek TUFE (Aylik) | 24sa | 42 | 1.53 | [1.23, 1.85] | 37 | -0.419 | [-0.689, -0.066] | 0.010 | hayır |
| Cekirdek TUFE (Aylik) | 48sa | 42 | 1.43 | [1.15, 1.74] | 37 | -0.173 | [-0.511, +0.168] | 0.307 | hayır |
| Cekirdek PCE (Aylik) | 1sa | 42 | 1.50 | [1.16, 1.85] | 35 | -0.114 | [-0.446, +0.220] | 0.513 | hayır |
| Cekirdek PCE (Aylik) | 4sa | 42 | 1.57 | [1.20, 1.98] | 35 | -0.041 | [-0.362, +0.303] | 0.815 | hayır |
| Cekirdek PCE (Aylik) | 24sa | 42 | 1.28 | [0.96, 1.64] | 35 | +0.164 | [-0.185, +0.471] | 0.345 | hayır |
| Cekirdek PCE (Aylik) | 48sa | 42 | 1.46 | [1.10, 1.88] | 35 | +0.183 | [-0.177, +0.487] | 0.293 | hayır |
| Perakende Satislar (Aylik) | 1sa | 44 | 1.40 | [1.06, 1.77] | 40 | -0.364 | [-0.612, -0.048] | 0.021 | hayır |
| Perakende Satislar (Aylik) | 4sa | 44 | 1.65 | [1.22, 2.16] | 40 | +0.041 | [-0.299, +0.382] | 0.803 | hayır |
| Perakende Satislar (Aylik) | 24sa | 44 | 1.05 | [0.79, 1.32] | 40 | +0.157 | [-0.172, +0.466] | 0.334 | hayır |
| Perakende Satislar (Aylik) | 48sa | 44 | 1.13 | [0.90, 1.37] | 40 | +0.063 | [-0.273, +0.393] | 0.701 | hayır |
| ISM Uretim PMI | 1sa | 44 | 1.97 | [1.47, 2.62] | 39 | -0.182 | [-0.525, +0.183] | 0.267 | hayır |
| ISM Uretim PMI | 4sa | 44 | 1.43 | [0.97, 2.05] | 39 | +0.058 | [-0.281, +0.396] | 0.724 | hayır |
| ISM Uretim PMI | 24sa | 44 | 1.38 | [1.01, 1.85] | 39 | +0.309 | [-0.010, +0.570] | 0.056 | hayır |
| ISM Uretim PMI | 48sa | 44 | 1.31 | [0.99, 1.69] | 39 | +0.298 | [-0.052, +0.604] | 0.065 | hayır |
| GSYIH (Ceyreklik) | 1sa | 41 | 1.95 | [1.39, 2.58] | 36 | -0.471 | [-0.717, -0.136] | 0.004 | hayır |
| GSYIH (Ceyreklik) | 4sa | 41 | 1.47 | [1.13, 1.92] | 36 | -0.143 | [-0.455, +0.195] | 0.406 | hayır |
| GSYIH (Ceyreklik) | 24sa | 41 | 1.14 | [0.87, 1.42] | 36 | +0.011 | [-0.330, +0.341] | 0.949 | hayır |
| GSYIH (Ceyreklik) | 48sa | 41 | 1.14 | [0.84, 1.48] | 36 | +0.402 | [+0.082, +0.644] | 0.015 | hayır |

## FOMC faiz kararı (yalnız hareket büyüklüğü; tahmin verisi yok)

| Ufuk | n | Oran | %95 CI |
|---|---|---|---|
| 1sa | 29 | 3.33 | [2.35, 4.45] |
| 4sa | 29 | 2.79 | [2.00, 3.73] |
| 24sa | 29 | 1.71 | [1.26, 2.19] |
| 48sa | 29 | 1.44 | [0.98, 1.96] |

## Gecikmeli etki: ilk 4 saatlik tepki dışarıda bırakıldı (sonradan eklendi, KEŞİFSEL)

Soru: ilk tepkiden SONRAKI hareket (olay+4sa → +24sa / +48sa) normalden büyük mü ve sürpriz işaretiyle ilişkili mi? (24sa/48sa oranı, ilk anlık sıçramanın kalıcı olmasından da yükselebilir; bu bölüm onu ayırır.)

| Kapsam | Pencere | n | Oran | Oran %95 CI | n(ρ) | ρ | ρ %95 CI | p | BH |
|---|---|---|---|---|---|---|---|---|---|
| HAVUZLU | 4sa→24sa | 254 | 1.11 | [0.98, 1.24] | 225 | +0.074 | [-0.064, +0.211] | 0.271 | hayır |
| HAVUZLU | 4sa→48sa | 254 | 1.21 | [1.08, 1.34] | 225 | +0.114 | [-0.018, +0.240] | 0.087 | hayır |
| NFP (Tarim Disi Istihdam) | 4sa→24sa | 41 | 1.20 | [0.89, 1.54] | 38 | -0.115 | [-0.468, +0.220] | 0.493 | hayır |
| NFP (Tarim Disi Istihdam) | 4sa→48sa | 41 | 1.15 | [0.92, 1.42] | 38 | -0.031 | [-0.376, +0.277] | 0.855 | hayır |
| Cekirdek TUFE (Aylik) | 4sa→24sa | 42 | 1.12 | [0.81, 1.49] | 37 | -0.126 | [-0.400, +0.177] | 0.457 | hayır |
| Cekirdek TUFE (Aylik) | 4sa→48sa | 42 | 1.26 | [0.95, 1.59] | 37 | -0.008 | [-0.334, +0.335] | 0.961 | hayır |
| Cekirdek PCE (Aylik) | 4sa→24sa | 42 | 0.96 | [0.68, 1.24] | 35 | +0.320 | [-0.020, +0.596] | 0.061 | hayır |
| Cekirdek PCE (Aylik) | 4sa→48sa | 42 | 1.29 | [0.95, 1.64] | 35 | +0.313 | [-0.008, +0.584] | 0.067 | hayır |
| Perakende Satislar (Aylik) | 4sa→24sa | 44 | 0.92 | [0.71, 1.15] | 40 | +0.076 | [-0.218, +0.370] | 0.640 | hayır |
| Perakende Satislar (Aylik) | 4sa→48sa | 44 | 1.07 | [0.87, 1.29] | 40 | +0.033 | [-0.293, +0.343] | 0.839 | hayır |
| ISM Uretim PMI | 4sa→24sa | 44 | 1.38 | [1.04, 1.74] | 39 | +0.203 | [-0.121, +0.493] | 0.216 | hayır |
| ISM Uretim PMI | 4sa→48sa | 44 | 1.26 | [0.97, 1.57] | 39 | +0.233 | [-0.120, +0.534] | 0.153 | hayır |
| GSYIH (Ceyreklik) | 4sa→24sa | 41 | 1.06 | [0.76, 1.39] | 36 | +0.197 | [-0.149, +0.492] | 0.248 | hayır |
| GSYIH (Ceyreklik) | 4sa→48sa | 41 | 1.20 | [0.91, 1.51] | 36 | +0.526 | [+0.234, +0.734] | 0.001 | EVET |

BH düzeltmesi bu bölümdeki 14 testin tamamı üzerinden.

## Sınırlamalar

1. 24sa/48sa ufuklarda aynı pencerede başka yüksek önemli olaylar da fiyatı etkiler (karıştırıcı etki); taban noktaları bu karışıklığı kısmen taşıdığı için oran bunu kısmen dengeler, tamamen değil.
2. Keşifsel analiz: aile seçimi ve işaret eşlemesi veriye bakmadan önceden belirlendi, ama test sayısı yine de çoklu; BH düzeltmesi yalnızca bu tablodaki testleri kapsar.
3. Aile başına yaklaşık 45-50 olay: yalnızca büyük etkiler ayırt edilebilir (ρ için yaklaşık |ρ| > 0,3).
4. Aynı gün/saat yayınlanan olaylar (ör. GSYİH ve PCE) havuzda bağımsız sayıldı; güven aralıkları hafif iyimser olabilir.
5. ATR high-low ortalamasıdır (hafta sonu boşlukları hariç).

**İşaretleme:** sayılar [GERÇEK VERİ] (gerçek MT5 bar ve takvim). Bootstrap/taban örneklemi rastgelelik içerir, tohum=42. [ÇALIŞTIRILMADI] model eğitimi; kilitli dönem okunmadı.

## Sağlamlık kontrolü: GSYİH 4sa→48sa (sonradan, keşifsel)

- Spearman ρ = +0,526 (n=36, p=0,001); permütasyon p = 0,0016.
- İki yarı ayrı bakınca da pozitif: ilk yarı +0,43 (p=0,073), son yarı +0,55 (p=0,017); sürprizi en uç 3 olay çıkarılınca +0,53.
- Bu raporda hesaplanan 42 ρ testinin tamamına BH uygulanınca anlamlı kalan 2 testten biri (diğeri havuzlu 1sa); Bonferroni (42 test) en küçük p için 0,014.
- **Karıştırıcı:** 36 GSYİH olayının 32'sinde sonraki 48 saat içinde Çekirdek PCE açıklaması var; etki GSYİH'den mi PCE'den mi ayrılamıyor. Çekirdek PCE'nin kendi 4sa→48sa ρ'su da pozitif (+0,31, düzeltmesiz p=0,067).
- Aile ve pencere sonuçlar görüldükten sonra incelendi: doğrulanmamış hipotez, kanıt değil.
