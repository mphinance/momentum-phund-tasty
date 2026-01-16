from tastytrade import Session, Account, DXLinkStreamer
from tastytrade.dxfeed import Quote
from tastytrade.account import CurrentPosition, Transaction
from typing import List, Dict, Optional, Union
import os
import asyncio
from decimal import Decimal
import time
from datetime import date, datetime

class TastytradeService:
    def __init__(self):
        self.session: Optional[Session] = None
        self.accounts: List[Account] = []
        self._current_account: Optional[Account] = None
        self._last_activity: float = 0
        self._keep_alive_interval: int = 300  # 5 minutes

    async def login(self) -> bool:
        """Authenticates using environment variables."""
        try:
            client_secret = os.getenv('TASTYTRADE_CLIENT_SECRET')
            refresh_token = os.getenv('TASTYTRADE_REFRESH_TOKEN')
            
            if not client_secret or not refresh_token:
                print("Missing credentials")
                return False
                
            self.session = Session(client_secret, refresh_token)
            self._last_activity = time.time()
            return True
        except Exception as e:
            print(f"Login failed: {e}")
            return False

    async def validate_session(self) -> bool:
        """
        Validates if the current session is still active.
        Returns True if valid, False if needs re-auth.
        """
        if not self.session:
            return False
        
        try:
            # Make a lightweight API call to validate the session
            await Account.a_get(self.session)
            self._last_activity = time.time()
            return True
        except Exception as e:
            print(f"Session validation failed: {e}")
            return False

    async def ensure_session(self) -> bool:
        """
        Ensures we have a valid session, re-authenticating if necessary.
        Call this before any API operation.
        """
        if not self.session:
            return await self.login()
        
        # If recent activity, assume session is valid
        if time.time() - self._last_activity < self._keep_alive_interval:
            return True
        
        # Validate and re-auth if needed
        if not await self.validate_session():
            print("Session expired, re-authenticating...")
            self.session = None
            self.accounts = []
            return await self.login()
        
        return True

    async def keep_alive(self) -> bool:
        """
        Heartbeat to keep the session alive.
        Makes a lightweight API call to prevent token expiration.
        Returns True if session is still active.
        """
        if not await self.ensure_session():
            return False
        
        try:
            # Lightweight call - just get account info
            await Account.a_get(self.session)
            self._last_activity = time.time()
            print(f"Keep-alive successful at {time.strftime('%H:%M:%S')}")
            return True
        except Exception as e:
            print(f"Keep-alive failed: {e}")
            # Try to re-authenticate
            self.session = None
            return await self.login()

    async def get_accounts(self) -> List[Account]:
        """Fetches all available accounts."""
        if not self.session:
            return []
        
        try:
            self.accounts = await Account.a_get(self.session)
            if self.accounts and not self._current_account:
                self._current_account = self.accounts[0]
            return self.accounts
        except Exception as e:
            print(f"Failed to fetch accounts: {e}")
            return []

    async def get_balance(self, account: Optional[Account] = None) -> Dict[str, float]:
        """Fetches detailed balance metrics."""
        target_account = account or self._current_account
        if not target_account or not self.session:
            return {}
            
        try:
            balances = await target_account.a_get_balances(self.session)
            return {
                'net_liq': float(balances.net_liquidating_value),
                'equity_buying_power': float(balances.equity_buying_power)
            }
        except Exception as e:
            print(f"Failed to fetch balance: {e}")
            return {}

    async def get_positions(self, account: Optional[Account] = None) -> List[Dict]:
        """Fetches positions for the specified account."""
        target_account = account or self._current_account
        if not target_account or not self.session:
            return []

        try:
            # Get raw positions from SDK
            positions: List[CurrentPosition] = await target_account.a_get_positions(self.session)
            
            # Fetch real-time quotes
            quotes = {}
            if positions:
                try:
                    symbols = [p.symbol for p in positions]
                    async with DXLinkStreamer(self.session) as streamer:
                        await streamer.subscribe(Quote, symbols)
                        
                        # Collect quotes for a short duration
                        start_time = asyncio.get_event_loop().time()
                        while asyncio.get_event_loop().time() - start_time < 2.0: # 2s timeout
                            if len(quotes) >= len(symbols):
                                break
                            try:
                                # Non-blocking check? Streamer is async iterator usually or get_event
                                # Using wait_for to ensure we don't block forever
                                quote = await asyncio.wait_for(streamer.get_event(Quote), timeout=0.1)
                                if quote.event_symbol not in quotes:
                                    quotes[quote.event_symbol] = quote
                            except asyncio.TimeoutError:
                                continue
                except Exception as e:
                    print(f"Quote streaming error: {e}")
            
            # Process into display-friendly format
            processed_positions = []
            for p in positions:
                # Calculate P/L and formatted values
                quantity = float(p.quantity)
                if p.quantity_direction == 'Short':
                    quantity = -quantity
                
                avg_open_price = float(p.average_open_price)
                
                # Determine current price (Mark)
                # Priority: 1. Live Quote  2. Position Mark  3. Fallback
                current_price = avg_open_price # Default
                
                if p.symbol in quotes:
                    q = quotes[p.symbol]
                    # Mid price logic
                    if q.bid_price and q.ask_price:
                        current_price = (float(q.bid_price) + float(q.ask_price)) / 2
                    elif q.bid_price:
                        current_price = float(q.bid_price)
                    elif q.ask_price:
                        current_price = float(q.ask_price)
                elif p.mark_price is not None:
                    current_price = float(p.mark_price)
                
                # Multiplier
                multiplier = float(p.multiplier)
                
                # Calculate unrealized P/L
                # (Current - Cost) * Qty * Multiplier
                unrealized_pl = (current_price - avg_open_price) * quantity * multiplier
                
                # Cost Basis for P/L %
                cost_basis = avg_open_price * abs(quantity) * multiplier
                p_l_percent = (unrealized_pl / cost_basis * 100) if cost_basis > 0 else 0.0

                pos_data = {
                    'symbol': p.symbol,
                    'underlying_symbol': p.underlying_symbol,
                    'type': p.instrument_type.name if hasattr(p.instrument_type, 'name') else str(p.instrument_type),
                    'quantity': int(quantity) if quantity.is_integer() else quantity,
                    'direction': p.quantity_direction,
                    'avg_open_price': avg_open_price,
                    'current_price': current_price,
                    'p_l': unrealized_pl,
                    'p_l_percent': p_l_percent,
                    'cost_basis': cost_basis,
                    'multiplier': multiplier
                }
                processed_positions.append(pos_data)
                
            return processed_positions
        except Exception as e:
            print(f"Failed to fetch positions: {e}")
            return []

    def get_dashboard_rows(self, raw_positions: List[Dict]) -> List[Dict]:
        """
        Processes positions into dashboard rows.
        - Bundles 'Covered Calls' (Long Equity + Short Call) into one row.
        - Leaves everything else (CSPs, Naked Options, Stock) as individual rows.
        """
        from collections import defaultdict
        
        # Group by underlying to detect strategies
        groups = defaultdict(list)
        for p in raw_positions:
            groups[p['underlying_symbol']].append(p)
            
        final_rows = []
        
        for underlying, legs in groups.items():
            # Check for Covered Call: Has Equity (Long) AND Short Call
            equities = [l for l in legs if l['type'] == 'Equity' and l['quantity'] > 0]
            short_calls = [l for l in legs if l['type'] == 'Option' and 'Call' in l['symbol'] and l['direction'] == 'Short']
            
            if equities and short_calls:
                # Identify legs to bundle
                # For simplicity in this 'View', we bundle ALL equity and ALL short calls for this underlying
                # as the 'Covered Call' package, and leave others (like Puts) separate.
                
                bundle_legs = equities + short_calls
                other_legs = [l for l in legs if l not in bundle_legs]
                
                # Create Composite Row
                total_pl = sum(l['p_l'] for l in bundle_legs)
                total_cost = sum(l['cost_basis'] for l in bundle_legs)
                total_pl_pct = (total_pl / total_cost * 100) if total_cost > 0 else 0.0
                
                # Heuristic for grouping symbol/qty
                qty_repr = f"{sum(l['quantity'] for l in equities)} / {sum(l['quantity'] for l in short_calls)}"
                
                composite_row = {
                    'symbol': f"{underlying} (CC)",
                    'type': 'Covered Call',
                    'direction': 'Net Long',
                    'quantity': qty_repr,
                    'avg_open_price': 0, # Mixed
                    'current_price': 0,  # Mixed
                    'p_l': total_pl,
                    'p_l_percent': total_pl_pct,
                    'is_composite': True,
                    'description': f"Shares & Short Calls"
                }
                final_rows.append(composite_row)
                final_rows.extend(other_legs)
            else:
                # No bundling, just add all legs
                final_rows.extend(legs)
                
        return final_rows

    @property
    def current_account(self) -> Optional[Account]:
        return self._current_account

    @current_account.setter
    def current_account(self, account: Account):
        self._current_account = account

    async def get_transactions(self, account: Optional[Account] = None, start_date: Optional[date] = None) -> List[Dict]:
        """
        Fetches transaction history for the specified account.
        
        :param account: The account to fetch transactions for.
        :param start_date: Start date for transactions (defaults to Jan 1 of current year).
        """
        target_account = account or self._current_account
        if not target_account or not self.session:
            return []
        
        try:
            # Default to YTD if no start date provided
            if start_date is None:
                start_date = date(datetime.now().year, 1, 1)
            
            transactions: List[Transaction] = await target_account.a_get_history(
                self.session,
                start_date=start_date,
                sort='Desc'
            )
            
            # Process into display-friendly format
            processed = []
            for t in transactions:
                processed.append({
                    'id': t.id,
                    'date': t.executed_at.strftime('%Y-%m-%d %H:%M') if t.executed_at else '',
                    'type': t.transaction_type,
                    'sub_type': t.transaction_sub_type,
                    'description': t.description,
                    'symbol': t.symbol or '',
                    'action': t.action.value if t.action else '',
                    'quantity': float(t.quantity) if t.quantity else 0,
                    'price': float(t.price) if t.price else 0,
                    'value': float(t.value),
                    'net_value': float(t.net_value),
                    'commission': float(t.commission) if t.commission else 0,
                    'fees': float(t.regulatory_fees or 0) + float(t.clearing_fees or 0),
                })
            
            return processed
        except Exception as e:
            print(f"Failed to fetch transactions: {e}")
            return []

    async def get_ytd_deposits(self, account: Optional[Account] = None) -> float:
        """
        Gets total deposits for the current year.
        Used for YTD return calculation: (Net Liq - Deposits) / Deposits
        """
        target_account = account or self._current_account
        if not target_account or not self.session:
            return 0.0
        
        try:
            start_of_year = date(datetime.now().year, 1, 1)
            
            # Fetch only money movement transactions
            transactions: List[Transaction] = await target_account.a_get_history(
                self.session,
                start_date=start_of_year,
                type='Money Movement',
                sort='Asc'
            )
            
            # Sum deposits (positive values typically)
            total_deposits = 0.0
            for t in transactions:
                if t.transaction_sub_type == 'Deposit':
                    total_deposits += float(t.value)
            
            return total_deposits
        except Exception as e:
            print(f"Failed to fetch deposits: {e}")
            return 0.0
