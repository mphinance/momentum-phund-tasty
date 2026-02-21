import asyncio
from services.tastytrade_api import TastytradeService
from dotenv import load_dotenv
import pprint

load_dotenv()

async def main():
    s = TastytradeService()
    if await s.login():
        accs = await s.get_accounts()
        if accs:
            # We need to access the raw balance object to see all fields
            # get_balance currently returns a dict, so we need to peek inside the method or duplicate logic
            # Let's simple call the SDK directly on the account
            acc = accs[0]
            bal = await acc.a_get_balances(s.session)
            print("Balance Fields:")
            # Print as dict if possible
            if hasattr(bal, 'dict'): # Pydantic v1
                pprint.pprint(bal.dict())
            elif hasattr(bal, 'model_dump'): # Pydantic v2
                pprint.pprint(bal.model_dump())
            else:
                pprint.pprint(bal.__dict__)

asyncio.run(main())
