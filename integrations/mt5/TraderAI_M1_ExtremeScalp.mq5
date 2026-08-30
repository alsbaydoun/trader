#property copyright "Trader AI Workstation"
#property version   "1.00"
#property strict
#property description "Confirmed M1 10/90 extreme reversal indicator. Signal and paper-log only."

#property indicator_chart_window
#property indicator_buffers 4
#property indicator_plots   4

#property indicator_label1  "Fast EMA"
#property indicator_type1   DRAW_LINE
#property indicator_color1  clrDeepSkyBlue
#property indicator_style1  STYLE_SOLID
#property indicator_width1  1

#property indicator_label2  "Slow EMA"
#property indicator_type2   DRAW_LINE
#property indicator_color2  clrDarkOrange
#property indicator_style2  STYLE_SOLID
#property indicator_width2  1

#property indicator_label3  "BUY 10"
#property indicator_type3   DRAW_ARROW
#property indicator_color3  clrLimeGreen
#property indicator_width3  2

#property indicator_label4  "SELL 90"
#property indicator_type4   DRAW_ARROW
#property indicator_color4  clrTomato
#property indicator_width4  2

input group "M1 reversal rules"
input int      RSITriggerPeriod       = 1;
input int      RSIConfirmationPeriod  = 3;
input int      RSIStructurePeriod     = 7;
input double   LowerExtreme            = 10.0;
input double   UpperExtreme            = 90.0;
input int      ExtremeLookbackBars    = 3;
input int      MinimumSignalScore     = 4;
input bool     RequireHigherTFBias    = true;
input ENUM_TIMEFRAMES BiasTimeframe   = PERIOD_M5;

input group "Confirmation filters"
input int      FastEMAPeriod          = 5;
input int      SlowEMAPeriod          = 20;
input int      MACDFastPeriod         = 5;
input int      MACDSlowPeriod         = 6;
input int      MACDSignalPeriod       = 3;
input int      ATRPeriod              = 14;
input double   MinimumATRPoints       = 0.0;
input int      MaximumSpreadPoints    = 0;
input bool     UseSessionFilter       = false;
input int      SessionStartHour       = 7;
input int      SessionEndHour         = 21;

input group "Paper trade view"
input double   StopATRMultiple        = 0.90;
input double   TargetRMultiple        = 1.15;
input bool     ShowTradeLevels        = true;
input bool     EnablePaperLog         = true;
input string   PaperLogFile           = "TraderAI-mt5-paper-signals.csv";

input group "Alerts"
input bool     EnableTerminalAlert    = true;
input bool     EnableSoundAlert       = true;
input string   SoundFile              = "alert.wav";
input bool     EnablePushAlert        = false;

double FastEMABuffer[];
double SlowEMABuffer[];
double BuyBuffer[];
double SellBuffer[];

double RSITrigger[];
double RSIConfirmation[];
double RSIStructure[];
double MACDMain[];
double MACDSignal[];
double ATRValues[];
double BiasEMA[];

int RSITriggerHandle = INVALID_HANDLE;
int RSIConfirmationHandle = INVALID_HANDLE;
int RSIStructureHandle = INVALID_HANDLE;
int MACDHandle = INVALID_HANDLE;
int ATRHandle = INVALID_HANDLE;
int FastEMAHandle = INVALID_HANDLE;
int SlowEMAHandle = INVALID_HANDLE;
int BiasEMAHandle = INVALID_HANDLE;

datetime LastAlertBar = 0;
string LastSignal = "WAIT";
string LastReason = "Waiting for a confirmed 10/90 reversal";
int LastScore = 0;
double LastSignalPrice = 0.0;
double LastSignalATR = 0.0;

string PanelBackground = "TraderAI_M1_Panel_Background";
string PanelTitle = "TraderAI_M1_Panel_Title";
string PanelStatus = "TraderAI_M1_Panel_Status";
string PanelMetrics = "TraderAI_M1_Panel_Metrics";
string PanelRules = "TraderAI_M1_Panel_Rules";
string PanelReason = "TraderAI_M1_Panel_Reason";
string EntryLine = "TraderAI_M1_Entry";
string StopLine = "TraderAI_M1_Stop";
string TargetLine = "TraderAI_M1_Target";

int OnInit()
  {
   if(Period() != PERIOD_M1)
     {
      Print("TraderAI M1 Extreme Scalp: attach this indicator to an M1 chart.");
     }

   SetIndexBuffer(0,FastEMABuffer,INDICATOR_DATA);
   SetIndexBuffer(1,SlowEMABuffer,INDICATOR_DATA);
   SetIndexBuffer(2,BuyBuffer,INDICATOR_DATA);
   SetIndexBuffer(3,SellBuffer,INDICATOR_DATA);

   ArraySetAsSeries(FastEMABuffer,true);
   ArraySetAsSeries(SlowEMABuffer,true);
   ArraySetAsSeries(BuyBuffer,true);
   ArraySetAsSeries(SellBuffer,true);

   PlotIndexSetInteger(2,PLOT_ARROW,233);
   PlotIndexSetInteger(3,PLOT_ARROW,234);
   PlotIndexSetDouble(2,PLOT_EMPTY_VALUE,EMPTY_VALUE);
   PlotIndexSetDouble(3,PLOT_EMPTY_VALUE,EMPTY_VALUE);

   RSITriggerHandle = iRSI(_Symbol,PERIOD_CURRENT,MathMax(1,RSITriggerPeriod),PRICE_CLOSE);
   RSIConfirmationHandle = iRSI(_Symbol,PERIOD_CURRENT,MathMax(2,RSIConfirmationPeriod),PRICE_CLOSE);
   RSIStructureHandle = iRSI(_Symbol,PERIOD_CURRENT,MathMax(3,RSIStructurePeriod),PRICE_CLOSE);
   MACDHandle = iMACD(_Symbol,PERIOD_CURRENT,MathMax(2,MACDFastPeriod),MathMax(3,MACDSlowPeriod),MathMax(2,MACDSignalPeriod),PRICE_CLOSE);
   ATRHandle = iATR(_Symbol,PERIOD_CURRENT,MathMax(2,ATRPeriod));
   FastEMAHandle = iMA(_Symbol,PERIOD_CURRENT,MathMax(2,FastEMAPeriod),0,MODE_EMA,PRICE_CLOSE);
   SlowEMAHandle = iMA(_Symbol,PERIOD_CURRENT,MathMax(3,SlowEMAPeriod),0,MODE_EMA,PRICE_CLOSE);
   BiasEMAHandle = iMA(_Symbol,BiasTimeframe,MathMax(3,SlowEMAPeriod),0,MODE_EMA,PRICE_CLOSE);

   if(RSITriggerHandle == INVALID_HANDLE || RSIConfirmationHandle == INVALID_HANDLE ||
      RSIStructureHandle == INVALID_HANDLE || MACDHandle == INVALID_HANDLE ||
      ATRHandle == INVALID_HANDLE || FastEMAHandle == INVALID_HANDLE ||
      SlowEMAHandle == INVALID_HANDLE || BiasEMAHandle == INVALID_HANDLE)
     {
      PrintFormat("TraderAI M1 Extreme Scalp: indicator handle creation failed, error=%d",GetLastError());
      return(INIT_FAILED);
     }

   CreatePanel();
   EventSetTimer(2);
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   ReleaseHandle(RSITriggerHandle);
   ReleaseHandle(RSIConfirmationHandle);
   ReleaseHandle(RSIStructureHandle);
   ReleaseHandle(MACDHandle);
   ReleaseHandle(ATRHandle);
   ReleaseHandle(FastEMAHandle);
   ReleaseHandle(SlowEMAHandle);
   ReleaseHandle(BiasEMAHandle);

   ObjectDelete(0,PanelBackground);
   ObjectDelete(0,PanelTitle);
   ObjectDelete(0,PanelStatus);
   ObjectDelete(0,PanelMetrics);
   ObjectDelete(0,PanelRules);
   ObjectDelete(0,PanelReason);
   ObjectDelete(0,EntryLine);
   ObjectDelete(0,StopLine);
   ObjectDelete(0,TargetLine);
  }

void OnTimer()
  {
   UpdatePanel();
  }

int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
  {
   int required_bars = MathMax(60,ExtremeLookbackBars+RSIStructurePeriod+10);
   if(rates_total < required_bars)
      return(0);

   ArraySetAsSeries(time,true);
   ArraySetAsSeries(open,true);
   ArraySetAsSeries(high,true);
   ArraySetAsSeries(low,true);
   ArraySetAsSeries(close,true);

   if(!CopySeries(rates_total))
      return(prev_calculated);

   int oldest_shift = rates_total - MathMax(ExtremeLookbackBars+RSIStructurePeriod+5,60);
   if(prev_calculated == 0)
     {
      ArrayInitialize(BuyBuffer,EMPTY_VALUE);
      ArrayInitialize(SellBuffer,EMPTY_VALUE);
      oldest_shift = rates_total - ExtremeLookbackBars - 4;
     }
   else
      oldest_shift = MathMin(oldest_shift,120);

   oldest_shift = MathMax(1,oldest_shift);
   for(int shift=oldest_shift;shift>=1;shift--)
     {
      BuyBuffer[shift] = EMPTY_VALUE;
      SellBuffer[shift] = EMPTY_VALUE;
      FastEMABuffer[shift] = FastEMAValue(shift);
      SlowEMABuffer[shift] = SlowEMAValue(shift);

      string direction = "";
      string reason = "";
      int score = 0;
      if(EvaluateSignal(shift,open,high,low,close,time,direction,reason,score))
        {
         double atr = ATRValues[shift];
         if(direction == "BUY")
            BuyBuffer[shift] = low[shift] - (atr*0.20);
         else if(direction == "SELL")
            SellBuffer[shift] = high[shift] + (atr*0.20);

         if(shift == 1)
           {
            LastSignal = direction;
            LastReason = reason;
            LastScore = score;
            LastSignalPrice = close[shift];
            LastSignalATR = atr;
            EmitSignalIfNew(time[shift],direction,reason,score,close[shift],atr);
           }
        }
      else if(shift == 1)
        {
         LastSignal = "WAIT";
         LastReason = reason;
         LastScore = score;
         LastSignalPrice = close[shift];
         LastSignalATR = ATRValues[shift];
        }
     }

   UpdatePanel();
   return(rates_total);
  }

bool CopySeries(const int rates_total)
  {
   ArraySetAsSeries(RSITrigger,true);
   ArraySetAsSeries(RSIConfirmation,true);
   ArraySetAsSeries(RSIStructure,true);
   ArraySetAsSeries(MACDMain,true);
   ArraySetAsSeries(MACDSignal,true);
   ArraySetAsSeries(ATRValues,true);
   ArraySetAsSeries(BiasEMA,true);

   int copied = CopyBuffer(RSITriggerHandle,0,0,rates_total,RSITrigger);
   if(copied < rates_total-5) return(false);
   copied = CopyBuffer(RSIConfirmationHandle,0,0,rates_total,RSIConfirmation);
   if(copied < rates_total-5) return(false);
   copied = CopyBuffer(RSIStructureHandle,0,0,rates_total,RSIStructure);
   if(copied < rates_total-5) return(false);
   copied = CopyBuffer(MACDHandle,0,0,rates_total,MACDMain);
   if(copied < rates_total-5) return(false);
   copied = CopyBuffer(MACDHandle,1,0,rates_total,MACDSignal);
   if(copied < rates_total-5) return(false);
   copied = CopyBuffer(ATRHandle,0,0,rates_total,ATRValues);
   if(copied < rates_total-5) return(false);
   copied = CopyBuffer(BiasEMAHandle,0,0,MathMax(100,rates_total),BiasEMA);
   return(copied > 5);
  }

double FastEMAValue(const int shift)
  {
   double values[];
   ArraySetAsSeries(values,true);
   if(CopyBuffer(FastEMAHandle,0,shift,1,values) != 1)
      return(0.0);
   return(values[0]);
  }

double SlowEMAValue(const int shift)
  {
   double values[];
   ArraySetAsSeries(values,true);
   if(CopyBuffer(SlowEMAHandle,0,shift,1,values) != 1)
      return(0.0);
   return(values[0]);
  }

bool EvaluateSignal(const int shift,
                    const double &open[],
                    const double &high[],
                    const double &low[],
                    const double &close[],
                    const datetime &time[],
                    string &direction,
                    string &reason,
                    int &score)
  {
   direction = "";
   score = 0;
   reason = "No confirmed setup";

   int lookback = MathMax(1,ExtremeLookbackBars);
   bool lower_extreme = false;
   bool upper_extreme = false;
   for(int offset=0;offset<lookback;offset++)
     {
      int index = shift+offset;
      if(index >= ArraySize(RSITrigger))
         break;
      lower_extreme = lower_extreme || RSITrigger[index] <= LowerExtreme;
      upper_extreme = upper_extreme || RSITrigger[index] >= UpperExtreme;
     }

   bool bullish_rejection = close[shift] > open[shift] && close[shift] > close[shift+1] &&
                            low[shift] <= low[shift+1];
   bool bearish_rejection = close[shift] < open[shift] && close[shift] < close[shift+1] &&
                            high[shift] >= high[shift+1];
   bool bullish_rsi = RSIConfirmation[shift] > RSIConfirmation[shift+1] &&
                      RSIStructure[shift] >= RSIStructure[shift+1];
   bool bearish_rsi = RSIConfirmation[shift] < RSIConfirmation[shift+1] &&
                      RSIStructure[shift] <= RSIStructure[shift+1];
   double macd_histogram = MACDMain[shift]-MACDSignal[shift];
   double prior_histogram = MACDMain[shift+1]-MACDSignal[shift+1];
   bool bullish_macd = macd_histogram > prior_histogram;
   bool bearish_macd = macd_histogram < prior_histogram;
   bool bullish_bias = HigherTimeframeBias(time[shift],true);
   bool bearish_bias = HigherTimeframeBias(time[shift],false);
   bool spread_ok = MaximumSpreadPoints <= 0 || CurrentSpreadPoints() <= MaximumSpreadPoints;
   bool volatility_ok = MinimumATRPoints <= 0.0 || (ATRValues[shift]/_Point) >= MinimumATRPoints;
   bool session_ok = SessionAllowed(time[shift]);

   if(lower_extreme)
      score++;
   if(bullish_rejection)
      score++;
   if(bullish_rsi)
      score++;
   if(bullish_macd)
      score++;
   if(bullish_bias || !RequireHigherTFBias)
      score++;

   if(lower_extreme && bullish_rejection && bullish_rsi && bullish_macd &&
      (!RequireHigherTFBias || bullish_bias) && spread_ok && volatility_ok && session_ok &&
      score >= MathMax(3,MinimumSignalScore))
     {
      direction = "BUY";
      reason = StringFormat("10 extreme + bullish rejection + RSI3/7 rising + MACD histogram rising%s",
                            RequireHigherTFBias ? " + higher-TF bullish bias" : "");
      return(true);
     }

   score = 0;
   if(upper_extreme)
      score++;
   if(bearish_rejection)
      score++;
   if(bearish_rsi)
      score++;
   if(bearish_macd)
      score++;
   if(bearish_bias || !RequireHigherTFBias)
      score++;

   if(upper_extreme && bearish_rejection && bearish_rsi && bearish_macd &&
      (!RequireHigherTFBias || bearish_bias) && spread_ok && volatility_ok && session_ok &&
      score >= MathMax(3,MinimumSignalScore))
     {
      direction = "SELL";
      reason = StringFormat("90 extreme + bearish rejection + RSI3/7 falling + MACD histogram falling%s",
                            RequireHigherTFBias ? " + higher-TF bearish bias" : "");
      return(true);
     }

   if(!spread_ok)
      reason = "Waiting: spread filter is blocking this setup";
   else if(!volatility_ok)
      reason = "Waiting: ATR volatility is below the configured minimum";
   else if(!session_ok)
      reason = "Waiting: outside the configured scalp session";
   else
      reason = StringFormat("Waiting for confirmation, score %d/%d",score,MathMax(3,MinimumSignalScore));
   return(false);
  }

bool HigherTimeframeBias(const datetime signal_time,const bool bullish)
  {
   if(!RequireHigherTFBias)
      return(true);
   int bias_shift = iBarShift(_Symbol,BiasTimeframe,signal_time,false);
   if(bias_shift < 0)
      return(false);

   double bias_close[];
   double bias_ema[];
   ArraySetAsSeries(bias_close,true);
   ArraySetAsSeries(bias_ema,true);
   if(CopyClose(_Symbol,BiasTimeframe,bias_shift,1,bias_close) != 1)
      return(false);
   if(CopyBuffer(BiasEMAHandle,0,bias_shift,1,bias_ema) != 1)
      return(false);
   return(bullish ? bias_close[0] >= bias_ema[0] : bias_close[0] <= bias_ema[0]);
  }

bool SessionAllowed(const datetime signal_time)
  {
   if(!UseSessionFilter)
      return(true);
   MqlDateTime stamp;
   TimeToStruct(signal_time,stamp);
   if(SessionStartHour <= SessionEndHour)
      return(stamp.hour >= SessionStartHour && stamp.hour < SessionEndHour);
   return(stamp.hour >= SessionStartHour || stamp.hour < SessionEndHour);
  }

int CurrentSpreadPoints()
  {
   long spread = 0;
   if(!SymbolInfoInteger(_Symbol,SYMBOL_SPREAD,spread))
      return(0);
   return((int)spread);
  }

void EmitSignalIfNew(const datetime signal_bar,
                     const string direction,
                     const string reason,
                     const int score,
                     const double entry,
                     const double atr)
  {
   if(signal_bar == LastAlertBar)
      return;
   LastAlertBar = signal_bar;

   double stop = direction == "BUY" ? entry-(atr*StopATRMultiple) : entry+(atr*StopATRMultiple);
   double target_distance = atr*StopATRMultiple*TargetRMultiple;
   double target = direction == "BUY" ? entry+target_distance : entry-target_distance;
   DrawTradeLevels(direction,entry,stop,target);
   WritePaperLog(signal_bar,direction,reason,score,entry,stop,target);

   string message = StringFormat("TraderAI PAPER %s %s M1 | score %d/%d | entry %s | %s",
                                 _Symbol,direction,score,MathMax(3,MinimumSignalScore),
                                 DoubleToString(entry,_Digits),reason);
   Print(message);
   if(EnableTerminalAlert)
      Alert(message);
   if(EnableSoundAlert)
      PlaySound(SoundFile);
   if(EnablePushAlert)
      SendNotification(message);
  }

void WritePaperLog(const datetime signal_bar,
                   const string direction,
                   const string reason,
                   const int score,
                   const double entry,
                   const double stop,
                   const double target)
  {
   if(!EnablePaperLog)
      return;
   int handle = FileOpen(PaperLogFile,FILE_READ|FILE_WRITE|FILE_CSV|FILE_COMMON|FILE_ANSI,';',CP_UTF8);
   if(handle == INVALID_HANDLE)
     {
      PrintFormat("TraderAI paper log: cannot open file, error=%d",GetLastError());
      return;
     }
   if(FileSize(handle) == 0)
      FileWrite(handle,"signal_time","symbol","timeframe","direction","score","entry","stop","target","reason");
   FileSeek(handle,0,SEEK_END);
   FileWrite(handle,TimeToString(signal_bar,TIME_DATE|TIME_SECONDS),_Symbol,"M1",direction,
             IntegerToString(score),DoubleToString(entry,_Digits),DoubleToString(stop,_Digits),
             DoubleToString(target,_Digits),reason);
   FileFlush(handle);
   FileClose(handle);
  }

void DrawTradeLevels(const string direction,const double entry,const double stop,const double target)
  {
   if(!ShowTradeLevels)
      return;
   SetHorizontalLine(EntryLine,entry,clrGold,STYLE_SOLID,2);
   SetHorizontalLine(StopLine,stop,clrTomato,STYLE_DASH,1);
   SetHorizontalLine(TargetLine,target,clrLimeGreen,STYLE_DASH,1);
   ObjectSetString(0,EntryLine,OBJPROP_TOOLTIP,StringFormat("PAPER %s entry",direction));
   ObjectSetString(0,StopLine,OBJPROP_TOOLTIP,"PAPER stop estimate");
   ObjectSetString(0,TargetLine,OBJPROP_TOOLTIP,"PAPER target estimate");
  }

void SetHorizontalLine(const string name,
                       const double price,
                       const color line_color,
                       const ENUM_LINE_STYLE style,
                       const int width)
  {
   if(ObjectFind(0,name) < 0)
      ObjectCreate(0,name,OBJ_HLINE,0,0,price);
   ObjectSetDouble(0,name,OBJPROP_PRICE,price);
   ObjectSetInteger(0,name,OBJPROP_COLOR,line_color);
   ObjectSetInteger(0,name,OBJPROP_STYLE,style);
   ObjectSetInteger(0,name,OBJPROP_WIDTH,width);
   ObjectSetInteger(0,name,OBJPROP_BACK,false);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,name,OBJPROP_HIDDEN,true);
  }

void CreatePanel()
  {
   CreateLabelBackground(PanelBackground,8,20,370,162,clrBlack,clrDimGray);
   CreateLabel(PanelTitle,18,30,clrWhite,10);
   CreateLabel(PanelStatus,18,54,clrWhite,9);
   CreateLabel(PanelMetrics,18,77,clrSilver,8);
   CreateLabel(PanelRules,18,101,clrSilver,8);
   CreateLabel(PanelReason,18,124,clrSilver,8);
   UpdatePanel();
  }

void CreateLabelBackground(const string name,
                           const int x,
                           const int y,
                           const int width,
                           const int height,
                           const color background,
                           const color border)
  {
   if(ObjectFind(0,name) < 0)
      ObjectCreate(0,name,OBJ_RECTANGLE_LABEL,0,0,0);
   ObjectSetInteger(0,name,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,name,OBJPROP_XDISTANCE,x);
   ObjectSetInteger(0,name,OBJPROP_YDISTANCE,y);
   ObjectSetInteger(0,name,OBJPROP_XSIZE,width);
   ObjectSetInteger(0,name,OBJPROP_YSIZE,height);
   ObjectSetInteger(0,name,OBJPROP_BGCOLOR,background);
   ObjectSetInteger(0,name,OBJPROP_BORDER_COLOR,border);
   ObjectSetInteger(0,name,OBJPROP_BACK,false);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,name,OBJPROP_HIDDEN,true);
  }

void CreateLabel(const string name,const int x,const int y,const color text_color,const int font_size)
  {
   if(ObjectFind(0,name) < 0)
      ObjectCreate(0,name,OBJ_LABEL,0,0,0);
   ObjectSetInteger(0,name,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,name,OBJPROP_XDISTANCE,x);
   ObjectSetInteger(0,name,OBJPROP_YDISTANCE,y);
   ObjectSetInteger(0,name,OBJPROP_COLOR,text_color);
   ObjectSetInteger(0,name,OBJPROP_FONTSIZE,font_size);
   ObjectSetString(0,name,OBJPROP_FONT,"Segoe UI");
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,name,OBJPROP_HIDDEN,true);
  }

 void UpdatePanel()
  {
   string timeframe = Period() == PERIOD_M1 ? "M1" : EnumToString((ENUM_TIMEFRAMES)Period());
   string title = StringFormat("TraderAI  %s  %s",_Symbol,timeframe);
   string status = StringFormat("PAPER ONLY   %s   score %d/%d",LastSignal,LastScore,MathMax(3,MinimumSignalScore));
   string metrics = StringFormat("RSI1 10/90 | RSI3 %.1f | RSI7 %.1f | ATR %s",
                                 ArraySize(RSIConfirmation) > 1 ? RSIConfirmation[1] : 0.0,
                                 ArraySize(RSIStructure) > 1 ? RSIStructure[1] : 0.0,
                                 DoubleToString(LastSignalATR,_Digits));
   string rules = StringFormat("M1 reversal | higher-TF bias %s",
                               RequireHigherTFBias ? "ON" : "OFF");
   ObjectSetString(0,PanelTitle,OBJPROP_TEXT,title);
   ObjectSetString(0,PanelStatus,OBJPROP_TEXT,status);
   ObjectSetString(0,PanelMetrics,OBJPROP_TEXT,metrics);
   ObjectSetString(0,PanelRules,OBJPROP_TEXT,rules);
   ObjectSetString(0,PanelReason,OBJPROP_TEXT,LastReason);
   ObjectSetInteger(0,PanelStatus,OBJPROP_COLOR,LastSignal == "BUY" ? clrLimeGreen : LastSignal == "SELL" ? clrTomato : clrGold);
   ChartRedraw(0);
  }

void ReleaseHandle(int &handle)
  {
   if(handle != INVALID_HANDLE)
     {
      IndicatorRelease(handle);
      handle = INVALID_HANDLE;
     }
  }
