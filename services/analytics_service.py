import pandas as pd
import quantstats_lumi as qs
import yfinance as yf
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CACHE_FILE = Path('analytics_cache.json')
SECTOR_CACHE_FILE = Path('sector_cache.json')

class AnalyticsService:
    def __init__(self):
        self._load_sector_cache()

    def _load_sector_cache(self):
        self.sector_cache = {}
        if SECTOR_CACHE_FILE.exists():
            try:
                self.sector_cache = json.loads(SECTOR_CACHE_FILE.read_text())
            except Exception as e:
                logger.error(f"Failed to load sector cache: {e}")

    def _save_sector_cache(self):
        try:
            SECTOR_CACHE_FILE.write_text(json.dumps(self.sector_cache, indent=2))
        except Exception as e:
            logger.error(f"Failed to save sector cache: {e}")

    def get_sector(self, symbol: str) -> str:
        """Fetches sector from YFinance with caching."""
        if symbol in self.sector_cache:
            return self.sector_cache[symbol]

        # Clean symbol for yfinance (e.g. " AMD" -> "AMD", remove precision bits if any)
        clean_symbol = symbol.strip().split(' ')[0]
        
        try:
            ticker = yf.Ticker(clean_symbol)
            sector = ticker.info.get('sector', 'Unknown')
            if sector and sector != 'Unknown':
                self.sector_cache[symbol] = sector
                return sector
        except Exception as e:
            logger.warning(f"Sector fetch failed for {symbol}: {e}")
        
        return 'Unknown'

    def compute(self, positions: List[Dict], transactions: List[Dict], balance: Dict) -> Dict:
        """
        Computes portfolio statistics and sector allocation.
        """
        logger.info("Computing analytics...")
        
        # 1. Sector Allocation
        sector_counts = {}
        total_value = 0.0
        
        for p in positions:
            val = p.get('total_value', 0.0)
            if val == 0:
                continue
                
            total_value += val
            sector = self.get_sector(p.get('symbol', ''))
            
            sector_counts[sector] = sector_counts.get(sector, 0.0) + val

        # Normalize to percentages
        sector_allocation = {}
        if total_value > 0:
            sector_allocation = {k: round(v / total_value * 100, 1) for k, v in sector_counts.items() if k != 'Unknown'}
        
        self._save_sector_cache()

        # Check for missing sectors
        standard_sectors = {
            'Technology', 'Healthcare', 'Energy', 'Financial Services', 
            'Consumer Cyclical', 'Consumer Defensive', 'Industrials', 
            'Basic Materials', 'Utilities', 'Real Estate', 'Communication Services'
        }
        present_sectors = set(sector_allocation.keys())
        missing_sectors = list(standard_sectors - present_sectors)

        # 2. Return Stats using QuantStats
        stats = {}
        try:
            df = pd.DataFrame(transactions)
            if not df.empty and 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                df['net_value'] = pd.to_numeric(df['net_value'], errors='coerce').fillna(0)
                
                # Daily PnL (Realized)
                daily_pnl = df.groupby(df['date'].dt.date)['net_value'].sum().sort_index()
                
                current_net_liq = float(balance.get('net_liq', 1.0))
                if current_net_liq == 0: current_net_liq = 1.0
                
                # Daily Return % (Approx)
                daily_returns = daily_pnl / current_net_liq
                daily_returns.index = pd.to_datetime(daily_returns.index)
                
                # Compute stats
                stats['sharpe'] = round(qs.stats.sharpe(daily_returns), 2)
                stats['sortino'] = round(qs.stats.sortino(daily_returns), 2)
                stats['calmar'] = round(qs.stats.calmar(daily_returns), 2)
                stats['max_drawdown'] = round(qs.stats.max_drawdown(daily_returns) * 100, 1)
                stats['volatility'] = round(qs.stats.volatility(daily_returns) * 100, 1)
                stats['win_rate'] = round(qs.stats.win_rate(daily_returns) * 100, 0)
                stats['var'] = round(qs.stats.var(daily_returns) * 100, 1)
                stats['best_day'] = round(daily_returns.max() * 100, 1) if not daily_returns.empty else 0.0
                stats['worst_day'] = round(daily_returns.min() * 100, 1) if not daily_returns.empty else 0.0

            else:
                stats['note'] = "No transaction history available"
                
        except Exception as e:
            logger.error(f"Stats computation failed: {e}")
            stats['note'] = "Error computing stats"

        return {
            'updated': datetime.now().isoformat(),
            'sector_allocation': sector_allocation,
            'missing_sectors': missing_sectors,
            'stats': stats
        }
