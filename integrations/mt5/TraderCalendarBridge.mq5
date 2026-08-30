#property copyright "Trader AI Workstation"
#property version   "1.00"
#property strict

input int    RefreshSeconds = 60;
input int    PastHours = 24;
input int    FutureDays = 7;
input string CurrencyFilter = "USD";
input string OutputFile = "TraderAI-calendar.csv";

int OnInit()
  {
   EventSetTimer(MathMax(15, RefreshSeconds));
   ExportCalendar();
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
  }

void OnTimer()
  {
   ExportCalendar();
  }

void ExportCalendar()
  {
   MqlCalendarValue values[];
   datetime server_now=TimeTradeServer();
   datetime date_from=server_now-(PastHours*60*60);
   datetime date_to=server_now+(FutureDays*24*60*60);
   int total=CalendarValueHistory(values,date_from,date_to,NULL,CurrencyFilter);
   if(total<0)
     {
      PrintFormat("TraderCalendarBridge: calendar request failed, error=%d",GetLastError());
      return;
     }

   int handle=FileOpen(OutputFile,FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,';',CP_UTF8);
   if(handle==INVALID_HANDLE)
     {
      PrintFormat("TraderCalendarBridge: output file failed, error=%d",GetLastError());
      return;
     }

   FileWrite(handle,
             "value_id","event_time_utc","country","currency","importance","sector",
             "name","source_url","actual","forecast","previous","currency_impact");

   long server_utc_offset=(long)(TimeTradeServer()-TimeGMT());
   for(int index=0;index<total;index++)
     {
      MqlCalendarEvent event;
      if(!CalendarEventById(values[index].event_id,event))
         continue;

      MqlCalendarCountry country;
      string country_name="";
      string currency=CurrencyFilter;
      if(CalendarCountryById(event.country_id,country))
        {
         country_name=country.name;
         currency=country.currency;
        }

      string actual="";
      string forecast="";
      string previous="";
      if(values[index].HasActualValue())
         actual=DoubleToString(values[index].GetActualValue(),event.digits);
      if(values[index].HasForecastValue())
         forecast=DoubleToString(values[index].GetForecastValue(),event.digits);
      if(values[index].HasPreviousValue())
         previous=DoubleToString(values[index].GetPreviousValue(),event.digits);

      long event_time_utc=(long)values[index].time-server_utc_offset;
      FileWrite(handle,
                (string)values[index].id,
                (string)event_time_utc,
                country_name,
                currency,
                (string)event.importance,
                (string)event.sector,
                event.name,
                event.source_url,
                actual,
                forecast,
                previous,
                (string)values[index].impact_type);
     }

   FileFlush(handle);
   FileClose(handle);
   PrintFormat("TraderCalendarBridge: exported %d calendar values",total);
  }
