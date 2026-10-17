//+------------------------------------------------------------------+
//|                                               CalendarExport.mq5 |
//|  ADIM 1: Zaman/veri hazirligi - ekonomik takvimi CSV'ye yazar     |
//|  MQL5 SCRIPT (EA degil). Ag kullanmaz, MT5 yerlesik takvimini     |
//|  okur. Ticaret mantigi icermez.                                   |
//|  NOT: Takvim fonksiyonlari SUNUCU saatini kullanir; CSV'de yalniz  |
//|  sunucu saati yazilir. UTC kolonu BILEREK yoktur (tek sabit kayma  |
//|  yaz/kis gecisinde yanlis olurdu).                                 |
//+------------------------------------------------------------------+
#property script_show_inputs
#property version   "1.00"

//=== AYARLAR (en ustte) =============================================
input datetime InpBaslangic   = D'2022.07.01 00:00'; // Baslangic (SUNUCU saati)
input datetime InpBitis       = 0;                    // Bitis (SUNUCU saati; 0 = simdi)
input string   InpDosyaAdi    = "calendar_events.csv";// FILE_COMMON altindaki dosya
input string   InpUlkeKodu    = "";                  // Ulke filtresi ("" = tum ulkeler)
input string   InpParaBirimi  = "";                   // Para birimi filtresi ("" = hepsi)
input int      InpTampon      = 200000;               // Baslangic dizi boyutu
//===================================================================

//+------------------------------------------------------------------+
//| Yardimci: CSV alanini guvenli hale getirir (virgul/tirnak)        |
//+------------------------------------------------------------------+
string CsvAlan(const string metin)
{
   string s = metin;
   StringReplace(s, "\"", "\"\"");      // icteki tirnaklari ikizle
   return "\"" + s + "\"";
}

//+------------------------------------------------------------------+
//| Yardimci: MqlCalendarValue degerini metne cevirir (LONG_MIN=bos)  |
//+------------------------------------------------------------------+
string DegerMetni(const long ham)
{
   if(ham == LONG_MIN) return "";       // deger yok
   return DoubleToString((double)ham / 1000000.0, 6);
}

//+------------------------------------------------------------------+
//| Yardimci: onem seviyesini okunur metne cevirir                    |
//+------------------------------------------------------------------+
string OnemMetni(const ENUM_CALENDAR_EVENT_IMPORTANCE onem)
{
   switch(onem)
   {
      case CALENDAR_IMPORTANCE_NONE:     return "none";
      case CALENDAR_IMPORTANCE_LOW:      return "low";
      case CALENDAR_IMPORTANCE_MODERATE: return "moderate";
      case CALENDAR_IMPORTANCE_HIGH:     return "high";
   }
   return "unknown";
}

//+------------------------------------------------------------------+
//| Yardimci: gecersiz datetime degerini metne cevirir                |
//+------------------------------------------------------------------+
string TarihMetni(const datetime t)
{
   if(t <= 0) return "";
   MqlDateTime y;
   TimeToStruct(t, y);
   return StringFormat("%04d-%02d-%02d %02d:%02d:%02d", y.year, y.mon, y.day, y.hour, y.min, y.sec);
}

//+------------------------------------------------------------------+
//| Yardimci: onbellek - olay aciklamalari (event_id -> MqlCalendarEvent)|
//+------------------------------------------------------------------+
struct OlayOnbellek
{
   ulong             id;
   MqlCalendarEvent  olay;
};

//+------------------------------------------------------------------+
//| Yardimci: onbellek - ulke aciklamalari (country_id -> MqlCalendarCountry)|
//+------------------------------------------------------------------+
struct UlkeOnbellek
{
   ulong               id;
   MqlCalendarCountry  ulke;
   bool                gecerli;
};

//+------------------------------------------------------------------+
//| Yardimci: olay aciklamasini onbellekten al, yoksa takvimden cek     |
//|  Ayni event_id tekrar tekrar sorgulanmaz (buyuk araliklarda cok     |
//|  onemli hiz kazanci).                                               |
//+------------------------------------------------------------------+
bool OlayGetir(const ulong event_id, OlayOnbellek &onbellek[], MqlCalendarEvent &olay)
{
   for(int i = 0; i < ArraySize(onbellek); i++)
      if(onbellek[i].id == event_id)
      {
         olay = onbellek[i].olay;
         return true;
      }

   MqlCalendarEvent yeni;
   if(!CalendarEventById(event_id, yeni))
      return false;

   int n = ArraySize(onbellek);
   if(ArrayResize(onbellek, n + 1) < 0)
   {
      PrintFormat("UYARI: olay onbellegi buyutulemedi (event_id=%I64u, hata %d).", event_id, GetLastError());
      olay = yeni;      // onbellege yazamadik ama degeri kullanilabilir
      return true;
   }
   onbellek[n].id   = event_id;
   onbellek[n].olay = yeni;
   olay = yeni;
   return true;
}

//+------------------------------------------------------------------+
//| Yardimci: ulke aciklamasini onbellekten al, yoksa takvimden cek     |
//|  Olay id'leri ile ayni mantik; basarisiz sonuc da onbellege yazilir |
//|  ki ayni eksik country_id tekrar sorgulanmasin.                     |
//+------------------------------------------------------------------+
bool UlkeGetir(const ulong country_id, UlkeOnbellek &onbellek[], MqlCalendarCountry &ulke)
{
   for(int i = 0; i < ArraySize(onbellek); i++)
      if(onbellek[i].id == country_id)
      {
         if(!onbellek[i].gecerli)
            return false;
         ulke = onbellek[i].ulke;
         return true;
      }

   MqlCalendarCountry yeni;
   bool gecerli = CalendarCountryById(country_id, yeni);

   int n = ArraySize(onbellek);
   if(ArrayResize(onbellek, n + 1) < 0)
   {
      PrintFormat("UYARI: ulke onbellegi buyutulemedi (country_id=%I64u, hata %d).", country_id, GetLastError());
      if(gecerli) ulke = yeni;
      return gecerli;
   }
   onbellek[n].id      = country_id;
   onbellek[n].ulke    = yeni;
   onbellek[n].gecerli = gecerli;
   if(gecerli) ulke = yeni;
   return gecerli;
}

//+------------------------------------------------------------------+
//| Ana: olaylari ceker, detaylari cozer, CSV'ye yazar                |
//+------------------------------------------------------------------+
void OnStart()
{
   //--- 1) Zaman araligini belirle (SUNUCU saati!)
   // Takvim fonksiyonlari sunucu saatini kullanir; bu yuzden giris ve cikis
   // tarihleri de SUNUCU saatindedir, UTC DEGIL.
   datetime tarihten = (InpBaslangic > 0) ? InpBaslangic : D'2022.07.01 00:00';
   datetime tarihe   = (InpBitis == 0) ? TimeTradeServer() : InpBitis;
   if(tarihe <= tarihten)
   {
      PrintFormat("HATA: Bitis zamani baslangictan once/eşit. Baslangic=%s Bitis=%s",
                  (string)tarihten, (string)tarihe);
      return;
   }

   //--- 2) BILGI AMACLI: sunucu-UTC kaymasi (takvim saatleri SUNUCU saatidir).
   //--- TimeGMT() son tam UTC saniyesini, TimeTradeServer() sunucu saatini verir.
   //--- Bu fark SADECE Journal'a ve dosya sonu NOT satirina yazilir; hicbir
   //--- satirin zamani bu farkla DEGISTIRILMEZ (tek sabit kayma yaz/kis
   //--- gecisinde yanlis olur).
   datetime simdiUTC    = TimeGMT();
   datetime simdiServer = TimeTradeServer();
   int      kaymaSn     = (int)(simdiServer - simdiUTC);
   PrintFormat("Bilgi: sunucu-UTC kaymasi = %+d saniye (%+.2f saat). Takvim saatleri SUNUCU saatidir; kayma sadece bilgi amacli yazilir.",
               kaymaSn, kaymaSn / 3600.0);

   //--- 3) Veri cekme (ag kullanilmaz, yerlesik takvim). Tampon yetmezse buyut.
   MqlCalendarValue degerler[];
   int adet = CalendarValueHistory(degerler, tarihten, tarihe, InpUlkeKodu, InpParaBirimi);
   if(adet < 0 && GetLastError() == 5400) // ERR_CALENDAR_MORE_DATA
   {
      int yeniBoy = InpTampon;
      bool basarili = false;
      for(int deneme = 0; deneme < 4; deneme++)
      {
         yeniBoy *= 4;
         if(ArrayResize(degerler, yeniBoy) < 0)
         {
            PrintFormat("HATA: ArrayResize basarisiz (hedef %d, hata %d).", yeniBoy, GetLastError());
            return;
         }
         ResetLastError();
         adet = CalendarValueHistory(degerler, tarihten, tarihe, InpUlkeKodu, InpParaBirimi);
         if(adet >= 0) { basarili = true; break; }
      }
      if(!basarili)
      {
         PrintFormat("HATA: CalendarValueHistory tampon buyutulerek de alinamadi. Son hata %d.", GetLastError());
         return;
      }
   }
   if(adet < 0)
   {
      PrintFormat("HATA: CalendarValueHistory basarisiz. Hata kodu=%d (5401=zaman asimi, 4001=ic hata).",
                  GetLastError());
      return;
   }
   if(adet == 0)
   {
      PrintFormat("UYARI: %s - %s araliginda hic olay donmedi. Takvimin indirilmis oldugundan emin olun.",
                  (string)tarihten, (string)tarihe);
      return;
   }
   PrintFormat("Bilgi: %d olay degeri alindi.", adet);

   //--- 4) Dosyayi ortak klasore (FILE_COMMON) yazma modunda ac
   // MQL5 NOTU: FILE_ANSI = sistem kod sayfasi (Turkce Windows'ta genelde cp1254).
   // MQL5'te BOM'suz tam UTF-8 yazma bayragi YOK: FILE_UNICODE = UTF-16LE'dir.
   // Bu yuzden kolon adlari ve "onem" degerleri ASCII tutuldu; Turkce karakter
   // iceren ulke/olay adlari sistem kod sayfasiyla yazilir ve Python tarafi
   // utf-8-sig -> utf-8 -> latin-1 fallback'i ile okur (kalite_kontrol.py).
   string dosyaYolu = InpDosyaAdi;   // FILE_COMMON sayesinde <TerminalDataFolder>\Common\Files
   int h = FileOpen(dosyaYolu, FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
   if(h == INVALID_HANDLE)
   {
      PrintFormat("HATA: Dosya acilamadi (%s). Hata kodu=%d. Ortak Files klasoru yazilabilir mi?",
                  dosyaYolu, GetLastError());
      return;
   }

   //--- 5) Baslik satiri + veri satirlari (kolon adlari ASCII: bkz. 4. adim notu)
   //--- Zaman kolonu TEK: takvimin verdigi SUNUCU saati. UTC kolonu yok.
   //--- event_id + ulke_kodu: filtreleme ISIM yerine KIMLIK ile yapilsin
   //--- (terminal dili Turkce oldugu icin isim eslesmesi kirilgan).
   FileWrite(h, "olay_zamani_sunucu", "ulke", "ulke_kodu", "para_birimi", "olay_adi",
             "event_id", "onem", "actual", "forecast", "previous");

   OlayOnbellek olayOnbellek[];   // event_id -> MqlCalendarEvent
   UlkeOnbellek ulkeOnbellek[];   // country_id -> MqlCalendarCountry
   int yazilan = 0;
   int atlanan = 0;
   for(int i = 0; i < adet; i++)
   {
      //--- olay aciklamasini onbellekli al (her satir icin tekrar sorgu yok)
      MqlCalendarEvent olay;
      if(!OlayGetir(degerler[i].event_id, olayOnbellek, olay))
      {
         PrintFormat("UYARI: CalendarEventById basarisiz (event_id=%I64u, hata %d). Satir atlandi.",
                     degerler[i].event_id, GetLastError());
         atlanan++;
         continue;
      }

      //--- ulke aciklamasini onbellekli al (isim + para birimi icin)
      MqlCalendarCountry ulke;
      bool ulkeOK = UlkeGetir(olay.country_id, ulkeOnbellek, ulke);
      if(!ulkeOK)
         PrintFormat("UYARI: CalendarCountryById basarisiz (country_id=%I64u, hata %d).",
                     olay.country_id, GetLastError());

      //--- Zaman: takvim degeri SUNUCU saatinde gelir, oldugu gibi yazilir.
      FileWrite(h,
                TarihMetni(degerler[i].time),           // olay zamani (broker sunucu saati)
                CsvAlan(ulkeOK ? ulke.name : ""),       // ulke adi
                CsvAlan(ulkeOK ? ulke.code : ""),       // ulke kodu (ISO 3166-1 alpha-2)
                CsvAlan(ulkeOK ? ulke.currency : ""),   // para birimi
                CsvAlan(olay.name),                     // olay adi (terminal dilinde)
                (string)degerler[i].event_id,           // event_id (dilden bagimsiz kimlik)
                OnemMetni(olay.importance),             // onem seviyesi
                DegerMetni(degerler[i].actual_value),   // actual
                DegerMetni(degerler[i].forecast_value), // forecast
                DegerMetni(degerler[i].prev_value));    // previous
      yazilan++;
   }

   //--- 6) Kayma bilgisini tasiyan NOT satiri + kapanis
   FileWrite(h, "", "", "", "",
             "NOT kayma_saniye=" + IntegerToString(kaymaSn) +
             " takvim_saati=SUNUCU; zaman kolonu degistirilmedi; python tarafi utf-8-sig/utf-8/cp1254/latin-1 ile okur",
             "", "", "", "", "");
   FileClose(h);

   PrintFormat("BILGI: %d satir yazildi, %d satir atlandi. Onbellek: %d olay / %d ulke.",
               yazilan, atlanan, ArraySize(olayOnbellek), ArraySize(ulkeOnbellek));
   PrintFormat("BILGI: Dosya: <TerminalDataFolder>/Common/Files/%s", dosyaYolu);
   PrintFormat("BILGI: Kodlama FILE_ANSI (sistem kod sayfasi). Tam UTF-8 yazim MQL5'te garanti degil; FILE_UNICODE alternatifi UTF-16LE uretir.");
}
//+------------------------------------------------------------------+
