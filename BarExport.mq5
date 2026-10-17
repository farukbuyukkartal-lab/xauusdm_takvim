//+------------------------------------------------------------------+
//|                                                    BarExport.mq5 |
//|  EK ADIM: XAUUSDm M15 mumlarini CopyRates ile CSV'ye yazar.       |
//|  MQL5 SCRIPT (EA degil). Ag kullanmaz. Ticaret mantigi icermez.   |
//|  Kolonlar: zaman_sunucu_epoch, zaman_sunucu, open, high, low,     |
//|            close, tick_volume                                     |
//+------------------------------------------------------------------+
#property script_show_inputs
#property version   "1.00"

//=== AYARLAR (en ustte) =============================================
input string   InpSembol      = "XAUUSDm";              // Sembol
input ENUM_TIMEFRAMES InpPeriyot = PERIOD_M15;          // Zaman dilimi
input datetime InpBaslangic   = D'2022.07.01 00:00';    // Baslangic (SUNUCU saati)
input datetime InpBitis       = 0;                      // Bitis (SUNUCU saati; 0 = simdi)
input string   InpDosyaAdi    = "bars_mql5.csv";        // FILE_COMMON altindaki dosya
input int      InpIlkBeklemeMs = 20000;                 // Ilk denemede bekleme suresi (ms)
input int      InpDenemeSayisi = 3;                     // Kac kez yeniden denenecek
//===================================================================

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
//| Yardimci: CopyRates'i yeniden denemeli sekilde cagirir.           |
//|  MT5 dokumani: veri yerel degilse indirme baslatilir ve fonksiyon |
//|  ilk cagrida 0/-1 donebilir; sonraki cagri daha fazla veri doner. |
//+------------------------------------------------------------------+
int MumlariCek(const string sembol, const ENUM_TIMEFRAMES periyot,
               const datetime bas, const datetime bit, MqlRates &mumlar[])
{
   for(int deneme = 1; deneme <= InpDenemeSayisi; deneme++)
   {
      ResetLastError();
      int adet = CopyRates(sembol, periyot, bas, bit, mumlar);
      if(adet > 0)
         return adet;

      PrintFormat("UYARI: CopyRates(%s) deneme %d/%d -> %d dondu. Hata=%d. %d ms bekleniyor.",
                  sembol, deneme, InpDenemeSayisi, adet, GetLastError(), InpIlkBeklemeMs);
      Sleep(InpIlkBeklemeMs);
   }
   return -1;   // tum denemeler basarisiz
}

//+------------------------------------------------------------------+
//| Ana: mumlari ceker ve CSV'ye yazar                                |
//+------------------------------------------------------------------+
void OnStart()
{
   //--- 1) Zaman araligini belirle (SUNUCU saati; grafik/series zamani ile ayni)
   datetime bas = (InpBaslangic > 0) ? InpBaslangic : D'2022.07.01 00:00';
   datetime bit = (InpBitis == 0) ? TimeTradeServer() : InpBitis;
   if(bit <= bas)
   {
      PrintFormat("HATA: Bitis zamani baslangictan once/esit. Baslangic=%s Bitis=%s",
                  TarihMetni(bas), TarihMetni(bit));
      return;
   }

   //--- 2) Sembolun hazir oldugundan emin ol (Market Watch + veri senkronu)
   if(!SymbolSelect(InpSembol, true))
   {
      PrintFormat("HATA: SymbolSelect(%s) basarisiz. Hata=%d. Sembol broker listesinde var mi?",
                  InpSembol, GetLastError());
      return;
   }
   if(!SymbolIsSynchronized(InpSembol))
   {
      PrintFormat("UYARI: %s verisi henuz senkron degil; veri indirilmesi tetikleniyor, bekleyin.", InpSembol);
      for(int i = 0; i < 30 && !SymbolIsSynchronized(InpSembol); i++)
         Sleep(1000);
      if(!SymbolIsSynchronized(InpSembol))
         PrintFormat("UYARI: %s hala senkron degil; CopyRates eksik veri dondurebilir.", InpSembol);
   }

   //--- 3) Mumlari cek (yeniden denemeli)
   MqlRates mumlar[];
   int adet = MumlariCek(InpSembol, InpPeriyot, bas, bit, mumlar);
   if(adet <= 0)
   {
      PrintFormat("HATA: CopyRates(%s, %s, %s - %s) hic veri donmedi. Son hata=%d. Olasi nedenler: "
                  "gecmis veri terminalde yok, TERMINAL_MAXBARS asildi, sembol adi yanlis.",
                  InpSembol, EnumToString(InpPeriyot), TarihMetni(bas), TarihMetni(bit), GetLastError());
      return;
   }

   //--- 4) MT5'in gercekten dondurdugu ILK ve SON bar (istenen araliktan farkli olabilir!)
   datetime gercekIlk = mumlar[0].time;
   datetime gercekSon = mumlar[adet - 1].time;
   PrintFormat("Bilgi: %d mum alindi. Gercek aralik: %s -> %s (istenen: %s -> %s)",
               adet, TarihMetni(gercekIlk), TarihMetni(gercekSon), TarihMetni(bas), TarihMetni(bit));
   if(gercekIlk > bas)
      PrintFormat("UYARI: istenen baslangictan sonraki ilk bar %s. Bu sembol/hesap icin daha eski M15 "
                  "gecmisi yok demektir; dosyaya yalnizca mevcut barlar yazilir.",
                  TarihMetni(gercekIlk));

   //--- 5) CSV'yi ortak klasore yaz
   int h = FileOpen(InpDosyaAdi, FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
   if(h == INVALID_HANDLE)
   {
      PrintFormat("HATA: Dosya acilamadi (%s). Hata=%d. Ortak Files klasoru yazilabilir mi?",
                  InpDosyaAdi, GetLastError());
      return;
   }

   FileWrite(h, "zaman_sunucu_epoch", "zaman_sunucu", "open", "high", "low", "close", "tick_volume");

   for(int i = 0; i < adet; i++)
   {
      FileWrite(h,
                (string)(long)mumlar[i].time,                 // zaman_sunucu_epoch (int)
                TarihMetni(mumlar[i].time),                   // zaman_sunucu (metin)
                DoubleToString(mumlar[i].open,  _Digits),     // open
                DoubleToString(mumlar[i].high,  _Digits),     // high
                DoubleToString(mumlar[i].low,   _Digits),     // low
                DoubleToString(mumlar[i].close, _Digits),     // close
                (string)mumlar[i].tick_volume);               // tick_volume
   }

   //--- 6) Bilgi satiri (python tarafi atlar) + kapanis
   FileWrite(h, "", "NOT sembol=" + InpSembol + " periyot=" + EnumToString(InpPeriyot) +
             " bar=" + IntegerToString(adet) + " kaynak=CopyRates zaman_dilimi=SUNUCU",
             "", "", "", "", "");
   FileClose(h);

   PrintFormat("BILGI: %d satir yazildi (%d bar + 1 NOT).", adet + 1, adet);
   PrintFormat("BILGI: Dosya: <TerminalDataFolder>/Common/Files/%s", InpDosyaAdi);
   PrintFormat("BILGI: Kodlama FILE_ANSI (sistem kod sayfasi). Tam UTF-8 MQL5'te garanti degil.");
}
//+------------------------------------------------------------------+
