#property copyright "Trader AI Workstation"
#property version   "1.00"
#property strict
#property description "Research-based trend and breakout EA. Tester trading enabled; live trading locked by default."

#include <Trade\Trade.mqh>

input group "Signal timeframe"
input ENUM_TIMEFRAMES EntryTimeframe      = PERIOD_CURRENT;
input ENUM_TIMEFRAMES BiasTimeframe       = PERIOD_H4;
input bool     RequireHigherTFBias         = true;

input group "Research trend rules"
input int      FastEMAPeriod               = 20;
input int      SlowEMAPeriod               = 50;
input int      BreakoutLookback            = 20;
input int      RSIPeriod                   = 14;
input double   BuyRSIThreshold             = 55.0;
input double   SellRSIThreshold            = 45.0;
input int      MACDFastPeriod              = 12;
input int      MACDSlowPeriod              = 26;
input int      MACDSignalPeriod            = 9;
input int      ADXPeriod                   = 14;
input double   MinimumADX                  = 18.0;
input int      ATRPeriod                   = 14;

input group "Risk and exits"
input double   RiskPerTradePercent         = 0.25;
input double   StopATRMultiple             = 1.50;
input double   TargetRMultiple             = 2.00;
input bool     UseBreakEven                = true;
input double   BreakEvenTriggerR           = 1.00;
input bool     UseATRTrailing              = true;
input double   TrailingATRMultiple         = 2.00;
input int      MaximumBarsInTrade          = 48;
input int      CooldownBars                = 3;
input int      MaximumOpenPositions        = 1;
input bool     CloseOnOppositeSignal       = true;

input group "Execution filters"
input int      MaximumSpreadPoints         = 0;
input bool     UseSessionFilter            = false;
input int      SessionStartHour            = 7;
input int      SessionEndHour              = 21;
input int      DeviationPoints             = 20;
input ulong    MagicNumber                 = 26082920;

input group "Safety boundary"
input bool     EnableStrategyTesterTrading = true;
input bool     EnableLiveTrading           = false;
input string   LiveTradingAcknowledgement  = "";
input bool     EnableTerminalAlerts        = true;
input bool     EnableSoundAlerts           = true;
input string   SoundFile                   = "alert.wav";

input group "Journal and panel"
input bool     EnableTradeLog              = true;
input string   TradeLogFile                = "TraderAI-research-trend-ea.csv";
input int      MinimumTradesForOptimization = 30;

CTrade Trade;

int FastEMAHandle = INVALID_HANDLE;
int SlowEMAHandle = INVALID_HANDLE;
int RSIHandle = INVALID_HANDLE;
int MACDHandle = INVALID_HANDLE;
int ADXHandle = INVALID_HANDLE;
int ATRHandle = INVALID_HANDLE;
int BiasEMAHandle = INVALID_HANDLE;

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

datetime LastEntryBar = 0;
datetime LastSignalBar = 0;
datetime LastTradeBar = 0;
string LastSignal = "WAIT";
string LastReason = "Waiting for a closed-bar setup";
int LastScore = 0;
double LastATR = 0.0;

const string RequiredLiveAcknowledgement = "I UNDERSTAND LIVE TRADING RISK";

ENUM_TIMEFRAMES ResolveEntryTimeframe()
  {
   if(EntryTimeframe == PERIOD_CURRENT)
      return((ENUM_TIMEFRAMES)_Period);
   return(EntryTimeframe);
  }

int OnInit()
  {
   ENUM_TIMEFRAMES timeframe = ResolveEntryTimeframe();
   if(timeframe == PERIOD_CURRENT || PeriodSeconds(timeframe) <= 0)
     {
      Print("TraderAI Research Trend EA: invalid entry timeframe");
      return(INIT_FAILED);
     }

   if(FastEMAPeriod < 2 || SlowEMAPeriod <= FastEMAPeriod ||
      BreakoutLookback < 2 || RSIPeriod < 2 || ATRPeriod < 2 ||
      StopATRMultiple <= 0.0 || TargetRMultiple <= 0.0 ||
      RiskPerTradePercent <= 0.0 || RiskPerTradePercent > 5.0)
     {
      Print("TraderAI Research Trend EA: invalid input values");
      return(INIT_PARAMETERS_INCORRECT);
     }

   FastEMAHandle = iMA(_Symbol,timeframe,FastEMAPeriod,0,MODE_EMA,PRICE_CLOSE);
   SlowEMAHandle = iMA(_Symbol,timeframe,SlowEMAPeriod,0,MODE_EMA,PRICE_CLOSE);
   RSIHandle = iRSI(_Symbol,timeframe,RSIPeriod,PRICE_CLOSE);
   MACDHandle = iMACD(_Symbol,timeframe,MACDFastPeriod,MACDSlowPeriod,MACDSignalPeriod,PRICE_CLOSE);
   ADXHandle = iADX(_Symbol,timeframe,ADXPeriod);
   ATRHandle = iATR(_Symbol,timeframe,ATRPeriod);
   BiasEMAHandle = iMA(_Symbol,BiasTimeframe,SlowEMAPeriod,0,MODE_EMA,PRICE_CLOSE);

   if(FastEMAHandle == INVALID_HANDLE || SlowEMAHandle == INVALID_HANDLE ||
      RSIHandle == INVALID_HANDLE || MACDHandle == INVALID_HANDLE ||
      ADXHandle == INVALID_HANDLE || ATRHandle == INVALID_HANDLE ||
      BiasEMAHandle == INVALID_HANDLE)
     {
      PrintFormat("TraderAI Research Trend EA: handle creation failed, error=%d",GetLastError());
      return(INIT_FAILED);
     }

   Trade.SetExpertMagicNumber(MagicNumber);
   Trade.SetDeviationInPoints(DeviationPoints);
   Trade.SetTypeFillingBySymbol(_Symbol);
   PrintFormat("TraderAI Research Trend EA: %s on %s; tester trading=%s; live trading=%s",
               EnumToString(timeframe),_Symbol,
               EnableStrategyTesterTrading ? "ON" : "OFF",
               EnableLiveTrading ? "REQUESTED" : "LOCKED");
   UpdatePanel();
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   ReleaseHandle(FastEMAHandle);
   ReleaseHandle(SlowEMAHandle);
   ReleaseHandle(RSIHandle);
   ReleaseHandle(MACDHandle);
   ReleaseHandle(ADXHandle);
   ReleaseHandle(ATRHandle);
   ReleaseHandle(BiasEMAHandle);
   Comment("");
  }

void OnTick()
  {
   ManageOpenPosition();
   if(!IsNewEntryBar())
      return;

   if(!RefreshValues())
     {
      LastReason = "Waiting: historical data is not ready";
      UpdatePanel();
      return;
     }

   string direction = "";
   string reason = "";
   int score = 0;
   double atr = 0.0;
   bool signal = EvaluateSignal(1,direction,reason,score,atr);
   LastSignal = signal ? direction : "WAIT";
   LastReason = reason;
   LastScore = score;
   LastATR = atr;
   UpdatePanel();

   if(!signal)
      return;
   if(LastSignalBar == iTime(_Symbol,ResolveEntryTimeframe(),1))
      return;
   LastSignalBar = iTime(_Symbol,ResolveEntryTimeframe(),1);

   double close_price = iClose(_Symbol,ResolveEntryTimeframe(),1);
   double stop = direction == "BUY" ? close_price-(atr*StopATRMultiple) : close_price+(atr*StopATRMultiple);
   double target_distance = MathAbs(close_price-stop)*TargetRMultiple;
   double target = direction == "BUY" ? close_price+target_distance : close_price-target_distance;
   WriteSignalLog(direction,score,close_price,stop,target,reason);
   EmitSignalAlert(direction,score,close_price,reason);

   if(!TradingAllowed())
     {
      LastReason = IsTester() ? "Signal found; tester trading is disabled" : "Signal only; real orders are locked";
      UpdatePanel();
      return;
     }

   if(!SessionAllowed(iTime(_Symbol,ResolveEntryTimeframe(),1)))
     {
      LastReason = "Signal blocked: outside configured session";
      UpdatePanel();
      return;
     }
   if(!SpreadAllowed())
     {
      LastReason = "Signal blocked: spread filter";
      UpdatePanel();
      return;
     }

   ulong ticket = 0;
   long position_type = -1;
   if(FindOurPosition(ticket,position_type))
     {
      if(CloseOnOppositeSignal &&
         ((direction == "BUY" && position_type == POSITION_TYPE_SELL) ||
          (direction == "SELL" && position_type == POSITION_TYPE_BUY)))
        {
         if(!Trade.PositionClose(ticket))
            PrintFormat("TraderAI Research Trend EA: opposite close failed, retcode=%u %s",
                        Trade.ResultRetcode(),Trade.ResultRetcodeDescription());
        }
      return;
     }

   if(!CooldownAllowed())
     {
      LastReason = "Signal blocked: cooldown after previous trade";
      UpdatePanel();
      return;
     }
   if(OpenPositionCount() >= MaximumOpenPositions)
     {
      LastReason = "Signal blocked: maximum open positions reached";
      UpdatePanel();
      return;
     }

   OpenTrade(direction,atr);
  }

bool IsNewEntryBar()
  {
   datetime current_bar = iTime(_Symbol,ResolveEntryTimeframe(),0);
   if(current_bar <= 0 || current_bar == LastEntryBar)
      return(false);
   LastEntryBar = current_bar;
   return(true);
  }

bool RefreshValues()
  {
   ENUM_TIMEFRAMES timeframe = ResolveEntryTimeframe();
   int required = MathMax(100,MathMax(SlowEMAPeriod, BreakoutLookback)+10);
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

   if(Bars(_Symbol,timeframe) < required)
      return(false);
   if(CopyBuffer(FastEMAHandle,0,0,required,FastEMAValues) < required-2) return(false);
   if(CopyBuffer(SlowEMAHandle,0,0,required,SlowEMAValues) < required-2) return(false);
   if(CopyBuffer(RSIHandle,0,0,required,RSIValues) < required-2) return(false);
   if(CopyBuffer(MACDHandle,0,0,required,MACDMainValues) < required-2) return(false);
   if(CopyBuffer(MACDHandle,1,0,required,MACDSignalValues) < required-2) return(false);
   if(CopyBuffer(ADXHandle,0,0,required,ADXValues) < required-2) return(false);
   if(CopyBuffer(ADXHandle,1,0,required,PlusDIValues) < required-2) return(false);
   if(CopyBuffer(ADXHandle,2,0,required,MinusDIValues) < required-2) return(false);
   if(CopyBuffer(ATRHandle,0,0,required,ATRValues) < required-2) return(false);
   if(CopyBuffer(BiasEMAHandle,0,0,MathMax(100,required),BiasEMAValues) < 10) return(false);
   return(ATRValues[1] > 0.0);
  }

bool EvaluateSignal(const int shift,
                    string &direction,
                    string &reason,
                    int &score,
                    double &atr)
  {
   direction = "";
   score = 0;
   atr = ATRValues[shift];
   reason = "No confirmed trend-breakout setup";
   ENUM_TIMEFRAMES timeframe = ResolveEntryTimeframe();
   if(atr <= 0.0 || shift+2 >= ArraySize(RSIValues))
      return(false);

   double open = iOpen(_Symbol,timeframe,shift);
   double close = iClose(_Symbol,timeframe,shift);
   double prior_close = iClose(_Symbol,timeframe,shift+1);
   double prior_high = iHigh(_Symbol,timeframe,iHighest(_Symbol,timeframe,MODE_HIGH,BreakoutLookback,shift+1));
   double prior_low = iLow(_Symbol,timeframe,iLowest(_Symbol,timeframe,MODE_LOW,BreakoutLookback,shift+1));
   double histogram = MACDMainValues[shift]-MACDSignalValues[shift];
   double prior_histogram = MACDMainValues[shift+1]-MACDSignalValues[shift+1];
   bool bullish_breakout = close > prior_high;
   bool bearish_breakout = close < prior_low;
   bool bullish_candle = close > open && close > prior_close;
   bool bearish_candle = close < open && close < prior_close;
   bool bullish_trend = close > FastEMAValues[shift] && FastEMAValues[shift] > SlowEMAValues[shift];
   bool bearish_trend = close < FastEMAValues[shift] && FastEMAValues[shift] < SlowEMAValues[shift];
   bool bullish_momentum = RSIValues[shift] >= BuyRSIThreshold &&
                           histogram > 0.0 && histogram > prior_histogram &&
                           PlusDIValues[shift] > MinusDIValues[shift];
   bool bearish_momentum = RSIValues[shift] <= SellRSIThreshold &&
                           histogram < 0.0 && histogram < prior_histogram &&
                           MinusDIValues[shift] > PlusDIValues[shift];
   bool trend_strength = ADXValues[shift] >= MinimumADX;
   bool bullish_bias = HigherTimeframeBias(iTime(_Symbol,timeframe,shift),true);
   bool bearish_bias = HigherTimeframeBias(iTime(_Symbol,timeframe,shift),false);

   bool buy_setup = bullish_breakout && bullish_candle && bullish_trend && bullish_momentum && trend_strength &&
                    (!RequireHigherTFBias || bullish_bias);
   bool sell_setup = bearish_breakout && bearish_candle && bearish_trend && bearish_momentum && trend_strength &&
                     (!RequireHigherTFBias || bearish_bias);

   if(buy_setup)
     {
      direction = "BUY";
      score = 6;
      reason = StringFormat("Donchian breakout + EMA trend + RSI %.1f + MACD rising + ADX %.1f%s",
                            RSIValues[shift],ADXValues[shift],
                            RequireHigherTFBias ? " + higher-TF bullish bias" : "");
      return(true);
     }
   if(sell_setup)
     {
      direction = "SELL";
      score = 6;
      reason = StringFormat("Donchian breakout + EMA trend + RSI %.1f + MACD falling + ADX %.1f%s",
                            RSIValues[shift],ADXValues[shift],
                            RequireHigherTFBias ? " + higher-TF bearish bias" : "");
      return(true);
     }

   int buy_score = (bullish_breakout ? 1 : 0) + (bullish_trend ? 1 : 0) +
                   (bullish_momentum ? 1 : 0) + (trend_strength ? 1 : 0) +
                   (bullish_bias ? 1 : 0) + (bullish_candle ? 1 : 0);
   int sell_score = (bearish_breakout ? 1 : 0) + (bearish_trend ? 1 : 0) +
                    (bearish_momentum ? 1 : 0) + (trend_strength ? 1 : 0) +
                    (bearish_bias ? 1 : 0) + (bearish_candle ? 1 : 0);
   score = MathMax(buy_score,sell_score);
   if(!trend_strength)
      reason = StringFormat("Waiting: ADX %.1f is below %.1f",ADXValues[shift],MinimumADX);
   else if(!bullish_breakout && !bearish_breakout)
      reason = StringFormat("Waiting: no %d-bar breakout",BreakoutLookback);
   else if(RequireHigherTFBias && !bullish_bias && !bearish_bias)
      reason = "Waiting: higher-timeframe bias is neutral";
   else
      reason = StringFormat("Waiting for confirmation, score %d/6",score);
   return(false);
  }

bool HigherTimeframeBias(const datetime signal_time,const bool bullish)
  {
   if(!RequireHigherTFBias)
      return(true);
   int bias_shift = iBarShift(_Symbol,BiasTimeframe,signal_time,false);
   if(PeriodSeconds(BiasTimeframe) > PeriodSeconds(ResolveEntryTimeframe()))
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

void OpenTrade(const string direction,const double atr)
  {
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol,tick))
      return;
   double entry = direction == "BUY" ? tick.ask : tick.bid;
   double stop_distance = atr*StopATRMultiple;
   double minimum_distance = MinimumStopDistance();
   stop_distance = MathMax(stop_distance,minimum_distance);
   double stop = direction == "BUY" ? entry-stop_distance : entry+stop_distance;
   double target_distance = stop_distance*TargetRMultiple;
   double target = direction == "BUY" ? entry+target_distance : entry-target_distance;
   stop = NormalizeDouble(stop,_Digits);
   target = NormalizeDouble(target,_Digits);

   double volume = CalculateVolume(entry,stop);
   if(volume <= 0.0)
     {
      LastReason = "Signal blocked: risk size is below broker minimum";
      UpdatePanel();
      return;
     }

   bool submitted = direction == "BUY"
                    ? Trade.Buy(volume,_Symbol,0.0,stop,target,"TraderAI Research Trend BUY")
                    : Trade.Sell(volume,_Symbol,0.0,stop,target,"TraderAI Research Trend SELL");
   if(!submitted || !TradeResultAccepted())
     {
      PrintFormat("TraderAI Research Trend EA: %s rejected, retcode=%u %s",
                  direction,Trade.ResultRetcode(),Trade.ResultRetcodeDescription());
      LastReason = "Signal rejected by broker/tester trade check";
      UpdatePanel();
      return;
     }

   LastTradeBar = iTime(_Symbol,ResolveEntryTimeframe(),0);
   LastReason = StringFormat("Opened tester trade: %s %.2f lots, stop %.5f, target %.5f",
                             direction,volume,stop,target);
   PrintFormat("TraderAI Research Trend EA: %s %.2f lots at %s, SL %s, TP %s",
               direction,volume,DoubleToString(entry,_Digits),
               DoubleToString(stop,_Digits),DoubleToString(target,_Digits));
   UpdatePanel();
  }

bool TradeResultAccepted()
  {
   uint retcode = Trade.ResultRetcode();
   return(retcode == TRADE_RETCODE_DONE || retcode == TRADE_RETCODE_DONE_PARTIAL ||
          retcode == TRADE_RETCODE_PLACED);
  }

double CalculateVolume(const double entry,const double stop)
  {
   double tick_size = SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   double tick_value = SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE_LOSS);
   if(tick_value <= 0.0)
      tick_value = SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double distance = MathAbs(entry-stop);
   if(tick_size <= 0.0 || tick_value <= 0.0 || distance <= 0.0)
      return(0.0);

   double risk_money = AccountInfoDouble(ACCOUNT_EQUITY)*(RiskPerTradePercent/100.0);
   double loss_per_lot = (distance/tick_size)*tick_value;
   double raw_volume = risk_money/loss_per_lot;
   double minimum = SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double maximum = SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   if(minimum <= 0.0 || maximum <= 0.0 || step <= 0.0 || raw_volume < minimum)
      return(0.0);
   double volume = MathMin(maximum,MathFloor(raw_volume/step)*step);
   if(volume < minimum)
      return(0.0);
   return(NormalizeDouble(volume,VolumeDigits(step)));
  }

int VolumeDigits(const double step)
  {
   int digits = 0;
   double value = step;
   while(digits < 8 && MathAbs(value-MathRound(value)) > 0.00000001)
     {
      value *= 10.0;
      digits++;
     }
   return(digits);
  }

void ManageOpenPosition()
  {
   ulong ticket = 0;
   long type = -1;
   if(!FindOurPosition(ticket,type))
      return;
   if(!RefreshCurrentATR())
      return;

   MqlTick tick;
   if(!SymbolInfoTick(_Symbol,tick))
      return;
   double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
   double current_sl = PositionGetDouble(POSITION_SL);
   double target = PositionGetDouble(POSITION_TP);
   double current_price = type == POSITION_TYPE_BUY ? tick.bid : tick.ask;
   double profit_distance = type == POSITION_TYPE_BUY ? current_price-open_price : open_price-current_price;
   double initial_risk = MathAbs(open_price-current_sl);
   if(initial_risk <= 0.0)
      initial_risk = LastATR*StopATRMultiple;
   double new_sl = current_sl;

   if(UseBreakEven && initial_risk > 0.0 && profit_distance >= initial_risk*BreakEvenTriggerR)
     {
      if(type == POSITION_TYPE_BUY && (new_sl <= 0.0 || new_sl < open_price))
         new_sl = open_price;
      if(type == POSITION_TYPE_SELL && (new_sl <= 0.0 || new_sl > open_price))
         new_sl = open_price;
     }
   if(UseATRTrailing && LastATR > 0.0 && profit_distance > 0.0)
     {
      double trail = LastATR*TrailingATRMultiple;
      double candidate = type == POSITION_TYPE_BUY ? current_price-trail : current_price+trail;
      if(type == POSITION_TYPE_BUY && candidate > new_sl && candidate < current_price)
         new_sl = candidate;
      if(type == POSITION_TYPE_SELL && (new_sl <= 0.0 || candidate < new_sl) && candidate > current_price)
         new_sl = candidate;
     }

   new_sl = NormalizeDouble(new_sl,_Digits);
   if(new_sl > 0.0 && MathAbs(new_sl-current_sl) >= _Point)
     {
      if(!Trade.PositionModify(ticket,new_sl,target))
         PrintFormat("TraderAI Research Trend EA: stop update failed, retcode=%u %s",
                     Trade.ResultRetcode(),Trade.ResultRetcodeDescription());
     }

   if(MaximumBarsInTrade > 0)
     {
      datetime open_time = (datetime)PositionGetInteger(POSITION_TIME);
      int bars_open = iBarShift(_Symbol,ResolveEntryTimeframe(),open_time,false);
      if(bars_open >= MaximumBarsInTrade)
        {
         if(!Trade.PositionClose(ticket))
            PrintFormat("TraderAI Research Trend EA: time exit failed, retcode=%u %s",
                        Trade.ResultRetcode(),Trade.ResultRetcodeDescription());
        }
     }
  }

bool RefreshCurrentATR()
  {
   ArraySetAsSeries(ATRValues,true);
   if(CopyBuffer(ATRHandle,0,0,3,ATRValues) < 2)
      return(false);
   LastATR = ATRValues[1] > 0.0 ? ATRValues[1] : ATRValues[0];
   return(LastATR > 0.0);
  }

bool FindOurPosition(ulong &ticket,long &type)
  {
   for(int index=PositionsTotal()-1;index>=0;index--)
     {
      ulong candidate = PositionGetTicket(index);
      if(candidate == 0 || !PositionSelectByTicket(candidate))
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC) != MagicNumber)
         continue;
      ticket = candidate;
      type = PositionGetInteger(POSITION_TYPE);
      return(true);
     }
   return(false);
  }

int OpenPositionCount()
  {
   int count = 0;
   for(int index=PositionsTotal()-1;index>=0;index--)
     {
      ulong ticket = PositionGetTicket(index);
      if(ticket == 0 || !PositionSelectByTicket(ticket))
         continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
         (ulong)PositionGetInteger(POSITION_MAGIC) == MagicNumber)
         count++;
     }
   return(count);
  }

bool TradingAllowed()
  {
   if(IsTester())
      return(EnableStrategyTesterTrading);
   if(!EnableLiveTrading)
      return(false);
   if(LiveTradingAcknowledgement != RequiredLiveAcknowledgement)
      return(false);
   return(true);
  }

bool IsTester()
  {
   return(MQLInfoInteger(MQL_TESTER) != 0);
  }

bool CooldownAllowed()
  {
   if(CooldownBars <= 0 || LastTradeBar <= 0)
      return(true);
   int bars_since = iBarShift(_Symbol,ResolveEntryTimeframe(),LastTradeBar,false);
   return(bars_since < 0 || bars_since >= CooldownBars);
  }

bool SpreadAllowed()
  {
   if(MaximumSpreadPoints <= 0)
      return(true);
   long spread = 0;
   if(!SymbolInfoInteger(_Symbol,SYMBOL_SPREAD,spread))
      return(true);
   return(spread <= MaximumSpreadPoints);
  }

bool SessionAllowed(const datetime event_time)
  {
   if(!UseSessionFilter)
      return(true);
   MqlDateTime stamp;
   TimeToStruct(event_time,stamp);
   if(SessionStartHour <= SessionEndHour)
      return(stamp.hour >= SessionStartHour && stamp.hour < SessionEndHour);
   return(stamp.hour >= SessionStartHour || stamp.hour < SessionEndHour);
  }

double MinimumStopDistance()
  {
   long stops = 0;
   long freeze = 0;
   SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL,stops);
   SymbolInfoInteger(_Symbol,SYMBOL_TRADE_FREEZE_LEVEL,freeze);
   return(MathMax((double)stops,(double)freeze)*_Point + _Point);
  }

void EmitSignalAlert(const string direction,const int score,const double price,const string reason)
  {
   string message = StringFormat("TraderAI %s %s %s | score %d/6 | %s",
                                 _Symbol,EnumToString(ResolveEntryTimeframe()),direction,score,reason);
   Print(message);
   if(!EnableTerminalAlerts || IsTester())
      return;
   if(EnableTerminalAlerts)
      Alert(message);
   if(EnableSoundAlerts)
      PlaySound(SoundFile);
  }

void WriteSignalLog(const string direction,
                    const int score,
                    const double entry,
                    const double stop,
                    const double target,
                    const string reason)
  {
   if(!EnableTradeLog || MQLInfoInteger(MQL_OPTIMIZATION) || MQLInfoInteger(MQL_FORWARD))
      return;
   int handle = FileOpen(TradeLogFile,FILE_READ|FILE_WRITE|FILE_CSV|FILE_COMMON|FILE_ANSI,';',CP_UTF8);
   if(handle == INVALID_HANDLE)
     {
      PrintFormat("TraderAI Research Trend EA: log open failed, error=%d",GetLastError());
      return;
     }
   if(FileSize(handle) == 0)
      FileWrite(handle,"signal_time","symbol","timeframe","direction","score","entry","stop","target","reason");
   FileSeek(handle,0,SEEK_END);
   FileWrite(handle,TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS),_Symbol,
             EnumToString(ResolveEntryTimeframe()),direction,IntegerToString(score),
             DoubleToString(entry,_Digits),DoubleToString(stop,_Digits),DoubleToString(target,_Digits),reason);
   FileFlush(handle);
   FileClose(handle);
  }

void UpdatePanel()
  {
   string mode = IsTester() ? "STRATEGY TESTER" : "SIGNAL ONLY - LIVE ORDERS LOCKED";
   string timeframe = EnumToString(ResolveEntryTimeframe());
   string position = OpenPositionCount() > 0 ? "POSITION OPEN" : "FLAT";
   Comment("TraderAI Research Trend EA\n",
           mode," | ",_Symbol," ",timeframe," | ",position,"\n",
           "PAPER/TESTER RULE: Donchian ",BreakoutLookback," + EMA ",FastEMAPeriod,"/",SlowEMAPeriod,
           " + RSI/MACD + ADX\n",
           "Status: ",LastSignal," | score ",LastScore,"/6 | ATR ",DoubleToString(LastATR,_Digits),"\n",
           "Risk ",DoubleToString(RiskPerTradePercent,2),"% | SL ",DoubleToString(StopATRMultiple,2),
           " ATR | TP ",DoubleToString(TargetRMultiple,2),"R | H4 bias ",RequireHigherTFBias ? "ON" : "OFF","\n",
           LastReason);
  }

double OnTester()
  {
   double trades = TesterStatistics(STAT_TRADES);
   if(trades < MinimumTradesForOptimization)
      return(-1000000.0 + trades);

   double profit = TesterStatistics(STAT_PROFIT);
   double drawdown = TesterStatistics(STAT_EQUITY_DDREL_PERCENT);
   double profit_factor = TesterStatistics(STAT_PROFIT_FACTOR);
   double initial_deposit = TesterStatistics(STAT_INITIAL_DEPOSIT);
   if(initial_deposit <= 0.0)
      initial_deposit = 1.0;
   if(profit_factor > 5.0)
      profit_factor = 5.0;
   if(profit_factor <= 0.0)
      profit_factor = 0.01;
   return((profit/initial_deposit)*profit_factor/(1.0+MathMax(0.0,drawdown)/10.0));
  }

void ReleaseHandle(int &handle)
  {
   if(handle != INVALID_HANDLE)
     {
      IndicatorRelease(handle);
      handle = INVALID_HANDLE;
     }
  }
