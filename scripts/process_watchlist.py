#!/usr/bin/env python3
import csv
import json
import os
import sys

# columns: symbol,name,sector,price,strike,capital,dte,roc_weekly,expiry

def process_watchlist(input_csv_path, output_json_path):
    print(f"Processing watchlist from {input_csv_path}...")
    
    if not os.path.exists(input_csv_path):
        print(f"Error: Could not find input file: {input_csv_path}")
        return False
        
    watchlist_data = []
    
    try:
        with open(input_csv_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            # Normalize field names to lowercase and strip whitespace
            if reader.fieldnames:
                reader.fieldnames = [str(x).strip().lower() for x in reader.fieldnames]
                
            for row in reader:
                try:
                    # Parse numeric fields safely
                    price = float(row.get('price', 0))
                    strike = float(row.get('strike', 0))
                    capital = float(row.get('capital', 0))
                    dte = int(float(row.get('dte', 0)))
                    roc_weekly = float(row.get('roc_weekly', 0))
                    
                    item = {
                        "symbol": row.get('symbol', '').strip(),
                        "name": row.get('name', '').strip(),
                        "sector": row.get('sector', '').strip(),
                        "price": price,
                        "strike": strike,
                        "capital": capital,
                        "dte": dte,
                        "roc_weekly": round(roc_weekly, 2),
                        "expiry": row.get('expiry', '').strip()
                    }
                    
                    # Only add rows that have a symbol
                    if item["symbol"]:
                        watchlist_data.append(item)
                except Exception as row_error:
                    print(f"Warning: Failed to parse row {row}: {row_error}")
                    continue
                    
        # Sort by ROC weekly descending by default
        watchlist_data.sort(key=lambda x: x.get('roc_weekly', 0), reverse=True)
        
        # Ensure docs folder exists
        os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
        
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(watchlist_data, f, indent=2)
            
        print(f"Successfully processed {len(watchlist_data)} watchlist items to {output_json_path}")
        return True
    
    except Exception as e:
        print(f"Error processing watchlist: {e}")
        return False

# Usage example if run directly:
if __name__ == "__main__":
    # Wait for actual file path or script integration context from the user
    pass
