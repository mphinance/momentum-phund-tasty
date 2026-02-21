#!/usr/bin/env python3
import json
import os
import sys

# Add current directory to path so we can import wheel_scanner
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from wheel_scanner import WheelScanner

def process_watchlist(output_json_path):
    print(f"Generating watchlist to {output_json_path}...")
    
    scanner = WheelScanner()
    
    # Parameters provided by user from "Fixing Scan History Accumulation" conversation
    config = {
        'min_price': 1.0,
        'max_price': 500.0,
        'max_capital': 50000.0, # derived max_price will be 500
        'min_roc_weekly': 1.0,  # Min Weekly ROC %
        'max_adx': 45,          # Max ADX
        'min_volume': 150000,   # Min Stock Vol
        'min_option_volume': 100, # Min Opt Vol
        'weekly_only': True,    # Filters: Weekly Only
        'golden_cross': True,   # Filters: Golden Cross
        'ema_atr_filter': True, # Filters: Near EMA20
        'tv_limit': 150,        # Default TV limit
        'max_results': 15,      # Limit the sidebar items
        'process_limit': 150    # Limit the total stocks processed to avoid rate limits
    }
    
    # Run scan
    results_df = scanner.scan(config)
    
    if results_df.empty:
        print("No results found from scan.")
        watchlist_data = []
    else:
        # Convert DataFrame to list of dicts for JSON
        # Filter and structure according to the requested columns:
        # symbol, name, sector, price, strike, capital, dte, roc_weekly, expiry
        
        watchlist_data = []
        for _, row in results_df.iterrows():
            item = {
                "symbol": row.get('symbol', ''),
                "name": row.get('name', ''),
                "sector": row.get('sector', ''),
                "price": float(row.get('price', 0)),
                "strike": float(row.get('strike', 0)),
                "capital": float(row.get('capital', 0)),
                "dte": int(row.get('dte', 0)),
                "roc_weekly": round(float(row.get('roc_weekly', 0)), 2),
                "expiry": row.get('expiry', '')
            }
            watchlist_data.append(item)
    
    # Save to JSON
    os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(watchlist_data, f, indent=2)
        
    print(f"Successfully generated {len(watchlist_data)} watchlist items to {output_json_path}")
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1:
        out_path = sys.argv[1]
    else:
        out_path = os.path.join(os.path.dirname(current_dir), 'docs', 'watchlist.json')
    
    process_watchlist(out_path)
