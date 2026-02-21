import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from services.tastytrade_api import TastytradeService

def get_analytics_data():
    """Tries to read the local analytics cache."""
    # Assuming this script runs in the same directory as main.py and analytics_cache.json
    cache_path = Path('analytics_cache.json')
    if not cache_path.exists():
        # Fallback for when running on Vultr specifically if paths differ
        cache_path = Path('/home/mphinance/tt/analytics_cache.json')
        
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text())
        except Exception as e:
            print(f"Error reading analytics cache: {e}")
            
    return None

async def export_dashboard_data():
    print("Starting data export...")
    load_dotenv()
    service = TastytradeService()
    
    if not await service.login():
        print("Login failed! Check .env credentials.")
        return False

    accounts = await service.get_accounts()
    if not accounts:
        print("No accounts found.")
        return False
        
    selected_account = accounts[0]
    print(f"Using account: {selected_account}")

    # Fetch Data
    print("Fetching balance...")
    balance = await service.get_balance(selected_account)
    net_liq = balance.get('net_liq', 0.0)
    
    print("Fetching positions...")
    raw_rows = await service.get_positions(selected_account)
    
    # Compute pct_portfolio
    for p in raw_rows:
        tv = p.get('total_value', 0)
        p['pct_portfolio'] = round(tv / net_liq * 100, 2) if net_liq > 0 else 0.0
        
    # Process for hybrid view (CC grouping)
    positions = service.get_dashboard_rows(raw_rows)
    
    print("Fetching transactions & deposits...")
    transactions = await service.get_transactions(selected_account)
    ytd_deposits = await service.get_ytd_deposits(selected_account)
    
    # Fetch Analytics
    analytics = get_analytics_data()

    # Construct the master JSON payload
    export_payload = {
        'last_refresh': datetime.now().isoformat(),
        'balance': balance,
        'ytd_deposits': ytd_deposits,
        'positions': positions,
        'transactions': transactions,
        'analytics': analytics
    }

    # Ensure docs directory exists
    docs_dir = Path('docs')
    docs_dir.mkdir(exist_ok=True)
    
    out_path = docs_dir / 'data.json'
    print(f"Writing payload to {out_path}...")
    
    with open(out_path, 'w') as f:
        json.dump(export_payload, f, indent=2)
        
    print("Export complete!")
    return True

if __name__ == "__main__":
    asyncio.run(export_dashboard_data())
