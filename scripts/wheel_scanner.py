import pandas as pd
import numpy as np
import yfinance as yf
from tradingview_screener import Query, col
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
import json

class WheelScanner:
    def __init__(self):
        self.is_scanning = False
        self.log_callback: Optional[Callable[[str], None]] = None

    def log(self, message: str):
        if self.log_callback:
            self.log_callback(message)
        print(message)

    def run_tv_screen(self, config: Dict[str, Any]) -> pd.DataFrame:
        """
        Run TradingView screen.
        Derives max_price from max_capital if not explicitly set (redundancy fix).
        """
        # Redundancy Fix: Calculate max_price from max_capital
        # 1 option contract = 100 shares.
        # Max Stock Price = Max Capital / 100
        max_capital = config.get('max_capital', 50000)
        derived_max_price = max_capital / 100.0
        
        # Use simple 500 as default max_price if not constrained, but cap at derived
        # If user explicitly provided max_price in config, use min of both
        config_max_price = config.get('max_price', 500.0)
        final_max_price = min(config_max_price, derived_max_price)
        
        self.log(f"═══════════════════════════════════════════════════")
        self.log(f"📊 STAGE 1: TradingView Pre-Filter (Server-side)")
        self.log(f"═══════════════════════════════════════════════════")
        self.log(f"  Price Range: ${config.get('min_price', 1.0):.2f} - ${final_max_price:.2f}")
        self.log(f"  Min Volume: {config.get('min_volume', 150000):,}")
        self.log(f"  Max ADX: {config.get('max_adx', 45)}")
        self.log(f"  Golden Cross: {'✓' if config.get('golden_cross', True) else '✗'}")

        conditions = [
            col('exchange') != "OTC",
            col('close').between(config.get('min_price', 1.0), final_max_price),
            col('average_volume_30d_calc') > config.get('min_volume', 150000),
            col('ADX').between(0, config.get('max_adx', 45)),
        ]
        
        if config.get('min_rsi') is not None:
             conditions.append(col('RSI').between(config.get('min_rsi', 0), config.get('max_rsi', 100)))

        # Optional Filter: Golden Cross (SMA50 > SMA200)
        if config.get('golden_cross', True):
            conditions.append(col('SMA50') > col('SMA200'))

        # TradingView Limit: default to 150 (app) but allow override (cron)
        tv_limit = config.get('tv_limit', 150)
        
        query = (
            Query().select(
                'name', 'close', 'market_cap_basic', 'average_volume_30d_calc',
                'ADX', 'RSI', 'sector', 'industry', 'Volatility.M',
                'SMA50', 'SMA200', 'EMA20', 'ATR'
            )
            .where(*conditions)
            .set_markets('america')
            .limit(tv_limit)
        )

        try:
            _, df = query.get_scanner_data()
            if df.empty:
                self.log("  ⚠️ No stocks passed TradingView filters")
                return pd.DataFrame()
            
            self.log(f"  ✓ TradingView returned: {len(df)} candidates (limit: {tv_limit})")

            df = df.rename(columns={
                'name': 'symbol',
                'close': 'price',
                'market_cap_basic': 'market_cap',
                'average_volume_30d_calc': 'avg_volume',
                'ADX': 'adx',
                'RSI': 'rsi',
                'Volatility.M': 'volatility_month',
                'SMA50': 'sma50',
                'SMA200': 'sma200',
                'EMA20': 'ema20',
                'ATR': 'atr'
            })
            
            # Optional Filter: Price within 1 ATR of EMA20
            self.log(f"")
            self.log(f"═══════════════════════════════════════════════════")
            self.log(f"📉 STAGE 2: Local Filters (No API cost)")
            self.log(f"═══════════════════════════════════════════════════")
            
            if config.get('ema_atr_filter', True):
                pre_filter_count = len(df)
                df['ema_diff'] = (df['price'] - df['ema20']).abs()
                df = df[df['ema_diff'] <= df['atr']]
                removed = pre_filter_count - len(df)
                pct = (removed / pre_filter_count * 100) if pre_filter_count > 0 else 0
                self.log(f"  EMA/ATR Filter (Near EMA20): {pre_filter_count} → {len(df)} ({removed} removed, {pct:.0f}%)")
            else:
                self.log(f"  EMA/ATR Filter: DISABLED")
            
            self.log(f"  ✓ Candidates for yfinance: {len(df)}")
            self.log(f"")
            self.log(f"═══════════════════════════════════════════════════")
            self.log(f"🔍 STAGE 3: yfinance API (1 call per stock)")
            self.log(f"═══════════════════════════════════════════════════")
            
            return df
        except Exception as e:
            self.log(f"TradingView Error: {e}")
            return pd.DataFrame()

    def fetch_wheel_data(self, symbol: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            stock = yf.Ticker(symbol, session=None)
            
            # Try to get info, but don't fail if it errors (leveraged ETFs often fail)
            try:
                info = stock.info
                price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
                company_name = info.get('shortName') or info.get('longName') or symbol
                div_yield = info.get('dividendYield', 0)
                div_yield = (div_yield * 100) if div_yield else 0
            except Exception:
                # Fallback: use history for price
                hist = stock.history(period="1d")
                if hist.empty:
                    return None
                price = float(hist['Close'].iloc[-1])
                company_name = symbol
                div_yield = 0
            
            if not price:
                return None

            # Get earnings date
            earnings_date = None
            try:
                cal = stock.calendar
                if cal is not None and not cal.empty:
                    if 'Earnings Date' in cal.index:
                        ed = cal.loc['Earnings Date']
                        if hasattr(ed, 'iloc') and len(ed) > 0:
                            earnings_date = str(ed.iloc[0].date()) if hasattr(ed.iloc[0], 'date') else str(ed.iloc[0])
                        else:
                            earnings_date = str(ed)
            except:
                pass  # Earnings date is optional

            expirations = stock.options
            if not expirations:
                return None

            today = datetime.now()
            
            # Sort expirations by date
            valid_exps = []
            for exp in expirations:
                dte = (datetime.strptime(exp, '%Y-%m-%d') - today).days
                if dte >= 2: # Minimum 2 days to avoid 0/1 DTE noise unless requested
                    valid_exps.append((exp, dte))
            
            valid_exps.sort(key=lambda x: x[1])
            
            if not valid_exps:
                return None

            # Weekly Options Filter: If enabled, only consider expirations within 14 days
            weekly_only = config.get('weekly_only', True)
            if weekly_only:
                weekly_exps = [(exp, dte) for exp, dte in valid_exps if dte <= 14]
                if not weekly_exps:
                    return None  # Skip this stock - no near-term options
                valid_exps = weekly_exps  # Only scan these!

            selected_data = None

            # Smart Expiration Scan: Find first expiration with >= Min ROC
            for target_exp, dte in valid_exps:
                try:
                    chain = stock.option_chain(target_exp).puts
                    
                    # Filter: ~10% OTM (Range 0.80 to 0.96 for broader catch)
                    puts = chain[
                        (chain['strike'] >= price * 0.80) & 
                        (chain['strike'] <= price * 0.96) & 
                        (chain['bid'] > 0)
                    ]

                    if puts.empty:
                        continue
                    
                    # Find closest to 0.90 (10% OTM)
                    puts = puts.copy()
                    puts['diff'] = abs(puts['strike'] - (price * 0.90))
                    best = puts.loc[puts['diff'].idxmin()]

                    capital_outlay = best['strike'] * 100
                    if capital_outlay > config.get('max_capital', 50000):
                        continue

                    mid = (best['bid'] + best['ask']) / 2
                    roc_period = (mid / best['strike']) * 100 # Total ROC
                    
                    weeks = max(dte, 1) / 7.0
                    roc_weekly = roc_period / weeks

                    iv = best.get('impliedVolatility', 0) * 100
                    
                    # Calculate total option volume for this expiration
                    opt_volume = int(chain['volume'].sum()) if 'volume' in chain.columns else 0
                    
                    # Option Volume Filter
                    min_opt_vol = config.get('min_option_volume', 100)
                    if opt_volume < min_opt_vol:
                        continue
                    
                    candidate_data = {
                        'symbol': symbol,
                        'name': company_name,
                        'price': price,
                        'strike': best['strike'],
                        'capital': capital_outlay, 
                        'dte': dte,
                        'iv': iv,
                        'premium': mid * 100, 
                        'roc_weekly': roc_weekly,
                        'roc_total': roc_period,
                        'div_yield': div_yield,
                        'expiry': target_exp,
                        'earnings': earnings_date or '',
                        'opt_vol': opt_volume
                    }

                    # IF return is good enough (> 1%), pick this and stop looking
                    min_roc_weekly = config.get('min_roc_weekly', 1.0)
                    if roc_weekly >= min_roc_weekly:
                        selected_data = candidate_data
                        break
                    
                except Exception:
                    continue
            
            return selected_data

        except Exception as e:
            return None

    def scan(self, config: Dict[str, Any], progress_callback=None) -> pd.DataFrame:
        self.is_scanning = True
        self.log("Starting scan...")
        
        tv_df = self.run_tv_screen(config)
        self.log(f"Found {len(tv_df)} candidates from TradingView.")

        if tv_df.empty:
            self.is_scanning = False
            return pd.DataFrame()

        min_roc = config.get('min_roc_weekly', 1.0)
        max_results = config.get('max_results', 20)
        
        results = []
        total_candidates = len(tv_df)
        
        # Limit processing to avoid timeouts/rate limits (configurable)
        process_limit = config.get('process_limit', 100) 
        processed = 0

        for i, row in tv_df.iterrows():
            if not self.is_scanning: 
                break
            
            if len(results) >= max_results:
                break
            
            if processed >= process_limit:
                self.log(f"Hit processing safety limit ({process_limit}). Stopping.")
                break

            sym = row['symbol']
            
            if progress_callback:
                progress_callback(processed + 1, total_candidates)
            
            data = self.fetch_wheel_data(sym, config)
            if data and data['roc_weekly'] >= min_roc:
                results.append(data)
                self.log(f"  [+] Found: {sym} | ROC: {data['roc_weekly']:.2f}% | Strike: {data['strike']}")
            
            processed += 1

        self.is_scanning = False
        
        # Summary stats
        self.log(f"")
        self.log(f"═══════════════════════════════════════════════════")
        self.log(f"📈 SCAN COMPLETE")
        self.log(f"═══════════════════════════════════════════════════")
        self.log(f"  Stocks checked: {processed}")
        self.log(f"  Valid opportunities: {len(results)}")
        self.log(f"  Success rate: {(len(results)/processed*100) if processed > 0 else 0:.1f}%")
        
        if not results:
            self.log("No opportunities found matching criteria.")
            return pd.DataFrame()

        final_df = pd.DataFrame(results)
        
        # Merge TV data
        final_df = final_df.merge(tv_df[['symbol', 'adx', 'rsi', 'sector']], on='symbol', how='left')
        
        # Score
        final_df['score'] = (final_df['roc_weekly'] * 20) + (final_df['div_yield'] * 5) - (final_df['rsi'] * 0.1)
        
        return final_df.sort_values('roc_weekly', ascending=False)
