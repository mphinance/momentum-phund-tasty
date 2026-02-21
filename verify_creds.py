import asyncio
from dotenv import load_dotenv
from services.tastytrade_api import TastytradeService
import os

load_dotenv()

async def main():
    service = TastytradeService()
    print("Testing credentials...")
    print(f"Secret present: {bool(os.getenv('TASTYTRADE_CLIENT_SECRET'))}")
    print(f"Token present: {bool(os.getenv('TASTYTRADE_REFRESH_TOKEN'))}")
    
    print("\nAttempting login...")
    if await service.login():
        print("Login SUCCESS!")
        
        print("\nFetching accounts...")
        accounts = await service.get_accounts()
        print(f"Found {len(accounts)} accounts")
        
        if accounts:
            acct = accounts[0]
            print(f"Using account: {acct.account_number}")
            
            print("\nFetching positions...")
            positions = await service.get_positions(acct)
            print(f"Found {len(positions)} positions")
            if positions:
                print("First position sample:")
                print(f"Symbol: {positions[0]['symbol']}")
                print(f"P/L: {positions[0]['p_l']}")
            else:
                print("No positions found (portfolio might be empty)")
    else:
        print("Login FAILED")

if __name__ == "__main__":
    asyncio.run(main())
