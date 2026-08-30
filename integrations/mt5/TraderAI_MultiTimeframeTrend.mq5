#property copyright "Trader AI Workstation"
#property version   "1.00"
#property strict
#property description "Multi-timeframe trend continuation indicator. Signal and paper-log only."

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

#property indicator_label3  "BUY trend"
#property indicator_type3  DRAW_ARROW
#property indicator_color3  clrLimeGreen
#property indicator_width3  2

#property indicator_label4  "SELL trend"
#property indicator_type4   DRAW_ARROW
#property indicator_color4  clrTomato
#property indicator_width4  2

input group "Analysis timeframe"
input ENUM_TIMEFRAMES AnalysisTimeframe = PERIOD_CURRENT;
input ENUM_TIMEFRAMES BiasTimeframe     = PERIOD_H4;
input bool     RequireHigherTFBias      = true;

input group "Trend confirmation"
input int      FastEMAPeriod            = 20;
input int      SlowEMAPeriod            = 50;
input int      RSIPeriod                = 14;
input double   BuyRSIThreshold          = 55.0;
input double   SellRSIThreshold         = 45.0;
input int      MACDFastPeriod           = 12;
input int      MACDSlowPeriod           = 26;
input int      MACDSignalPeriod         = 9;
input int      ADXPeriod                = 14;
input double   MinimumADX               = 18.0;
input int      ATRPeriod                = 14;

input group "Paper trade view"
input double   StopATRMultiple          = 1.20;
input double   TargetRMultiple          = 1.50;
input bool     ShowTradeLevels          = true;
input bool     EnablePaperLog           = true;
input string   PaperLogFile             = "TraderAI-mt5-trend-signals.csv";

input group "Filters"
input bool     UseSessionFilter         = false;
input int      SessionStartHour         = 7;
input int      SessionEndHour           = 21;
input int      MaximumSpreadPoints      = 0;

input group "Alerts"
input bool     EnableTerminalAlert      = true;
input bool     EnableSoundAlert         = true;
input string   SoundFile                = "alert.wav";
input bool     EnablePushAlert          = false;

double FastEMABuffer[];
double SlowEMABuffer[];
double BuyBuffer[];
double SellBuffer[];

double FastEMAValues[];
double SlowEMAValues[];
double RSIValues[];
double MACDMainValues[];
double MACDSignalValues[];
double ADXValues[];
double PlusDIValues[];
double MinusDIValues[];
double ATRValues[];
double BiasEMAValues[];

int FastEMAHandle = INVALID_HANDLE;
int SlowEMAHandle = INVALID_HANDLE;
int RSIHandle = INVALID_HANDLE;
int MACDHandle = INVALID_HANDLE;
int ADXHandle = INVALID_HANDLE;
int ATRHandle = INVALID_HANDLE;
int BiasEMAHandle = INVALID_HANDLE;

datetime LastAlertBar = 0;
string LastSignal = "WAIT";
string LastReason = "Waiting for a confirmed trend setup";
int LastScore = 0;
double LastSignalATR = 0.0;

string PanelBackground = "TraderAI_Trend_Panel_Background";
string PanelTitle = "TraderAI_Trend_Panel_Title";
string PanelStatus = "TraderAI_Trend_Panel_Status";
string PanelMetrics = "TraderAI_Trend_Panel_Metrics";
string PanelRules = "TraderAI_Trend_Panel_Rules";
string PanelReason = "TraderAI_Trend_Panel_Reason";
string EntryLine = "TraderAI_Trend_Entry";
string StopLine = "TraderAI_Trend_Stop";
string TargetLine = "TraderAI_Trend_Target";

ENUM_TIMEFRAMES ResolveTimeframe()
  {
   if(AnalysisTimeframe == PERIOD_CURRENT)
      return((ENUM_TIMEFRAMES)_Period);
   return(AnalysisTimeframe);
  }

int OnInit()
  {
   ENUM_TIMEFRAMES timeframe = ResolveTimeframe();
   if(timeframe == PERIOD_M1 || timeframe == PERIOD_M5 || timeframe == PERIOD_M15 ||
      timeframe == PERIOD_H1 || timeframe == PERIOD_H4 || timeframe == PERIOD_D1)
      PrintFormat("TraderAI Multi-timeframe Trend: analysing %s on %s",
                  EnumToString(timeframe),_Symbol);
   else
      Print("TraderAI Multi-timeframe Trend: attach it to a standard M5, M15, H1, H4 or D1 chart.");

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

   FastEMAHandle = iMA(_Symbol,timeframe,MathMax(2,FastEMAPeriod),0,MODE_EMA,PRICE_CLOSE);
   SlowEMAHandle = iMA(_Symbol,timeframe,MathMax(3,SlowEMAPeriod),0,MODE_EMA,PRICE_CLOSE);
   RSIHandle = iRSI(_Symbol,timeframe,MathMax(2,RSIPeriod),PRICE_CLOSE);
   MACDHandle = iMACD(_Symbol,timeframe,MathMax(2,MACDFastPeriod),
                     MathMax(3,MACDSlowPeriod),MathMax(2,MACDSignalPeriod),PRICE_CLOSE);
   ADXHandle = iADX(_Symbol,timeframe,MathMax(2,ADXPeriod));
   ATRHandle = iATR(_Symbol,timeframe,MathMax(2,ATRPeriod));
   BiasEMAHandle = iMA(_Symbol,BiasTimeframe,MathMax(3,SlowEMAPeriod),0,MODE_EMA,PRICE_CLOSE);

   if(FastEMAHandle == INVALID_HANDLE || SlowEMAHandle == INVALID_HANDLE ||
      RSIHandle == INVALID_HANDLE || MACDHandle == INVALID_HANDLE ||
      ADXHandle == INVALID_HANDLE || ATRHandle == INVALID_HANDLE ||
      BiasEMAHandle == INVALID_HANDLE)
     {
      PrintFormat("TraderAI Multi-timeframe Trend: indicator handle creation failed, error=%d",GetLastError());
      return(INIT_FAILED);
     }

   CreatePanel();
   EventSetTimer(2);
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   ReleaseHandle(FastEMAHandle);
   ReleaseHandle(SlowEMAHandle);
   ReleaseHandle(RSIHandle);
   ReleaseHandle(MACDHandle);
   ReleaseHandle(ADXHandle);
   ReleaseHandle(ATRHandle);
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
   int required_bars = MathMax(80,SlowEMAPeriod+ADXPeriod+ATRPeriod+10);
   if(rates_total < required_bars)
      return(0);

   ArraySetAsSeries(time,true);
   ArraySetAsSeries(open,true);
   ArraySetAsSeries(high,true);
   ArraySetAsSeries(low,true);
   ArraySetAsSeries(close,true);

   if(!CopySeries(rates_total))
      return(prev_calculated);

   int oldest_shift = rates_total - MathMax(required_bars,80);
   if(prev_calculated == 0)
     {
      ArrayInitialize(BuyBuffer,EMPTY_VALUE);
      ArrayInitialize(SellBuffer,EMPTY_VALUE);
      oldest_shift = rates_total - required_bars - 2;
     }
   else
      oldest_shift = MathMin(oldest_shift,120);

   oldest_shift = MathMax(1,oldest_shift);
   for(int shift=oldest_shift;shift>=1;shift--)
     {
      BuyBuffer[shift] = EMPTY_VALUE;
      SellBuffer[shift] = EMPTY_VALUE;
      FastEMABuffer[shift] = FastEMAValues[shift];
      SlowEMABuffer[shift] = SlowEMAValues[shift];

      string direction = "";
      string reason = "";
      int score = 0;
      if(EvaluateSignal(shift,open,high,low,close,time,direction,reason,score))
        {
         double atr = ATRValues[shift];
         if(direction == "BUY")
            BuyBuffer[shift] = low[shift] - (atr*0.25);
         else if(direction == "SELL")
            SellBuffer[shift] = high[shift] + (atr*0.25);

         if(shift == 1)
           {
            LastSignal = direction;
            LastReason = reason;
            LastScore = score;
            LastSignalATR = atr;
            EmitSignalIfNew(time[shift],direction,reason,score,close[shift],atr);
           }
        }
      else if(shift == 1)
        {
         LastSignal = "WAIT";
         LastReason = reason;
         LastScore = score;
         LastSignalATR = ATRValues[shift];
        }
     }

   UpdatePanel();
   return(rates_total);
  }

bool CopySeries(const int rates_total)
  {
   ArraySetAsSeries(FastEMAValues,true);
   ArraySetAsSeries(SlowEMAValues,true);
   ArraySetAsSeries(RSIValues,true);
   ArraySetAsSeries(MACDMainValues,true);
   ArraySetAsSeries(MACDSignalValues,true);
   ArraySetAsSeries(ADXValues,true);
   ArraySetAsSeries(PlusDIValues,true);
   ArraySetAsSeries(MinusDIValues,true);
   ArraySetAsSeries(ATRValues,true);
   ArraySetAsSeries(BiasEMAValues,true);

   int copied = CopyBuffer(FastEMAHandle,0,0,rates_total,FastEMAValues);
   if(copied < rates_total-5) return(false);
   copied = CopyBuffer(SlowEMAHandle,0,0,rates_total,SlowEMAValues);
   if(copied < rates_total-5) return(false);
   copied = CopyBuffer(RSIHandle,0,0,rates_total,RSIValues);
   if(copied < rates_total-5) return(false);
   copied = CopyBuffer(MACDHandle,0,0,rates_total,MACDMainValues);
   if(copied < rates_total-5) return(false);
   copied = CopyBuffer(MACDHandle,1,0,rates_total,MACDSignalValues);
   if(copied < rates_total-5) return(false);
   copied = CopyBuffer(ADXHandle,0,0,rates_total,ADXValues);
   if(copied < rates_total-5) return(false);
   copied = CopyBuffer(ADXHandle,1,0,rates_total,PlusDIValues);
   if(copied < rates_total-5) return(false);
   copied = CopyBuffer(ADXHandle,2,0,rates_total,MinusDIValues);
   if(copied < rates_total-5) return(false);
   copied = CopyBuffer(ATRHandle,0,0,rates_total,ATRValues);
   if(copied < rates_total-5) return(false);
   copied = CopyBuffer(BiasEMAHandle,0,0,MathMax(100,rates_total),BiasEMAValues);
   return(copied > 5);
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
   reason = "No confirmed trend setup";
   if(shift+1 >= ArraySize(RSIValues) || ATRValues[shift] <= 0.0)
      return(false);

   bool bullish_bias = HigherTimeframeBias(time[shift],true);
   bool bearish_bias = HigherTimeframeBias(time[shift],false);
   bool spread_ok = MaximumSpreadPoints <= 0 || CurrentSpreadPoints() <= MaximumSpreadPoints;
   bool session_ok = SessionAllowed(time[shift]);
   bool bullish_candle = close[shift] > open[shift] && close[shift] > close[shift+1];
   bool bearish_candle = close[shift] < open[shift] && close[shift] < close[shift+1];
   bool bullish_trend = close[shift] > FastEMAValues[shift] &&
                        FastEMAValues[shift] > SlowEMAValues[shift];
   bool bearish_trend = close[shift] < FastEMAValues[shift] &&
                        FastEMAValues[shift] < SlowEMAValues[shift];
   double histogram = MACDMainValues[shift]-MACDSignalValues[shift];
   double prior_histogram = MACDMainValues[shift+1]-MACDSignalValues[shift+1];
   bool bullish_momentum = RSIValues[shift] >= BuyRSIThreshold &&
                           histogram > 0.0 && histogram > prior_histogram &&
                           PlusDIValues[shift] > MinusDIValues[shift];
   bool bearish_momentum = RSIValues[shift] <= SellRSIThreshold &&
                           histogram < 0.0 && histogram < prior_histogram &&
                           MinusDIValues[shift] > PlusDIValues[shift];
   bool trend_strength = ADXValues[shift] >= MinimumADX;

   bool buy_setup = bullish_candle && bullish_trend && bullish_momentum && trend_strength &&
                    (!RequireHigherTFBias || bullish_bias) && spread_ok && session_ok;
   bool sell_setup = bearish_candle && bearish_trend && bearish_momentum && trend_strength &&
                     (!RequireHigherTFBias || bearish_bias) && spread_ok && session_ok;
   bool prior_buy_setup = shift+1 < ArraySize(RSIValues) &&
                          close[shift+1] > open[shift+1] &&
                          close[shift+1] > FastEMAValues[shift+1] &&
                          FastEMAValues[shift+1] > SlowEMAValues[shift+1] &&
                          RSIValues[shift+1] >= BuyRSIThreshold &&
                          (MACDMainValues[shift+1]-MACDSignalValues[shift+1]) > 0.0 &&
                          PlusDIValues[shift+1] > MinusDIValues[shift+1];
   bool prior_sell_setup = shift+1 < ArraySize(RSIValues) &&
                           close[shift+1] < open[shift+1] &&
                           close[shift+1] < FastEMAValues[shift+1] &&
                           FastEMAValues[shift+1] < SlowEMAValues[shift+1] &&
                           RSIValues[shift+1] <= SellRSIThreshold &&
                           (MACDMainValues[shift+1]-MACDSignalValues[shift+1]) < 0.0 &&
                           MinusDIValues[shift+1] > PlusDIValues[shift+1];

   if(buy_setup && !prior_buy_setup)
     {
      direction = "BUY";
      score = 5;
      reason = StringFormat("EMA trend + RSI %.1f + MACD rising + ADX %.1f%s",
                            RSIValues[shift],ADXValues[shift],
                            RequireHigherTFBias ? " + higher-TF bullish bias" : "");
      return(true);
     }
   if(sell_setup && !prior_sell_setup)
     {
      direction = "SELL";
      score = 5;
      reason = StringFormat("EMA trend + RSI %.1f + MACD falling + ADX %.1f%s",
                            RSIValues[shift],ADXValues[shift],
                            RequireHigherTFBias ? " + higher-TF bearish bias" : "");
      return(true);
     }

   if(!spread_ok)
      reason = "Waiting: spread filter is blocking this setup";
   else if(!session_ok)
      reason = "Waiting: outside the configured trading session";
   else if(!trend_strength)
      reason = StringFormat("Waiting: ADX %.1f is below %.1f",ADXValues[shift],MinimumADX);
   else
     {
      int buy_score = (bullish_trend ? 1 : 0) + (bullish_momentum ? 1 : 0) +
                      (trend_strength ? 1 : 0) + (bullish_bias ? 1 : 0) +
                      (bullish_candle ? 1 : 0);
      int sell_score = (bearish_trend ? 1 : 0) + (bearish_momentum ? 1 : 0) +
                       (trend_strength ? 1 : 0) + (bearish_bias ? 1 : 0) +
                       (bearish_candle ? 1 : 0);
      score = MathMax(buy_score,sell_score);
      reason = StringFormat("Waiting for trend confirmation, score %d/5",score);
     }
   return(false);
  }

bool HigherTimeframeBias(const datetime signal_time,const bool bullish)
  {
   if(!RequireHigherTFBias)
      return(true);
   ENUM_TIMEFRAMES signal_tf = ResolveTimeframe();
   int bias_shift = iBarShift(_Symbol,BiasTimeframe,signal_time,false);
   if(PeriodSeconds(BiasTimeframe) > PeriodSeconds(signal_tf))
      bias_shift++;
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
   if(ShowTradeLevels)
      DrawTradeLevels(direction,entry,stop,target);
   WritePaperLog(signal_bar,direction,reason,score,entry,stop,target);

   string timeframe = EnumToString(ResolveTimeframe());
   string message = StringFormat("TraderAI PAPER %s %s %s | score %d/5 | entry %s | %s",
                                 _Symbol,timeframe,direction,score,
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
      PrintFormat("TraderAI trend paper log: cannot open file, error=%d",GetLastError());
      return;
     }
   if(FileSize(handle) == 0)
      FileWrite(handle,"signal_time","symbol","timeframe","direction","score","entry","stop","target","reason");
   FileSeek(handle,0,SEEK_END);
   FileWrite(handle,TimeToString(signal_bar,TIME_DATE|TIME_SECONDS),_Symbol,
             EnumToString(ResolveTimeframe()),direction,IntegerToString(score),
             DoubleToString(entry,_Digits),DoubleToString(stop,_Digits),
             DoubleToString(target,_Digits),reason);
   FileFlush(handle);
   FileClose(handle);
  }

void DrawTradeLevels(const string direction,const double entry,const double stop,const double target)
  {
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
   CreateLabelBackground(PanelBackground,8,20,400,162,clrBlack,clrDimGray);
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
   string timeframe = EnumToString(ResolveTimeframe());
   string title = StringFormat("TraderAI Trend  %s  %s",_Symbol,timeframe);
   string status = StringFormat("PAPER ONLY   %s   score %d/5",LastSignal,LastScore);
   string metrics = StringFormat("RSI %.1f | ADX %.1f | ATR %s",
                                 ArraySize(RSIValues) > 1 ? RSIValues[1] : 0.0,
                                 ArraySize(ADXValues) > 1 ? ADXValues[1] : 0.0,
                                 DoubleToString(LastSignalATR,_Digits));
   string rules = StringFormat("EMA %d/%d | MACD %d/%d/%d | bias %s",
                               FastEMAPeriod,SlowEMAPeriod,MACDFastPeriod,MACDSlowPeriod,
                               MACDSignalPeriod,RequireHigherTFBias ? "ON" : "OFF");
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
