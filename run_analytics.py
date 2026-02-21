import asyncio
import argparse
import json
import logging
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# Ensure we can import services
sys.path.append(str(Path(__file__).parent))

from services.tastytrade_api import TastytradeService
from services.analytics_service import AnalyticsService

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("analytics.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("run_analytics")

async def main():
    logger.info("Starting analytics run...")
    
    # Initialize services
    tt_service = TastytradeService()
    analytics_service = AnalyticsService()
    
    # Login with retry
    retries = 3
    delay = 5
    
    logged_in = False
    for i in range(retries):
        if await tt_service.login():
            logger.info("Logged in successfully")
            logged_in = True
            break
        else:
            logger.warning(f"Login attempt {i+1} failed, retrying in {delay}s...")
            time.sleep(delay)
            
    if not logged_in:
        logger.error("Failed to login to Tastytrade after multiple attempts")
        return
    
    try:
        # Fetch Data
        accounts = await tt_service.get_accounts()
        if not accounts:
            logger.error("No accounts found")
            return
            
        account = accounts[0] # Default to first account
        logger.info(f"Using account: {account.account_number}")
        
        # Get Balance
        balance = await tt_service.get_balance(account)
        logger.info(f"Net Liq: {balance.get('net_liq')}")
        
        # Get Positions
        positions = await tt_service.get_positions(account)
        logger.info(f"Fetched {len(positions)} positions")
        
        # Get Transactions (YTD)
        transactions = await tt_service.get_transactions(account)
        logger.info(f"Fetched {len(transactions)} transactions YTD")
        
        # Compute Analytics
        result = analytics_service.compute(positions, transactions, balance)
        
        # Save to Cache
        cache_file = Path('analytics_cache.json')
        cache_file.write_text(json.dumps(result, indent=2))
        logger.info(f"Analytics saved to {cache_file.absolute()}")
        
    except Exception as e:
        logger.error(f"Error during execution: {e}", exc_info=True)
    finally:
        # Cleanup if needed
        pass

if __name__ == "__main__":
    asyncio.run(main())
