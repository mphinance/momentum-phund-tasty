from nicegui import ui, app
from services.tastytrade_api import TastytradeService
from dotenv import load_dotenv
import asyncio
from collections import defaultdict

# Load environment variables
load_dotenv()

# Service instance
service = TastytradeService()

# Styling
app.add_static_files('/static', 'static')

def format_currency(value):
    return f"${value:,.2f}"

def format_color(value):
    return 'text-green-400' if value >= 0 else 'text-red-400'

@ui.page('/')
async def main_page():
    # Dark mode and base styles
    ui.colors(primary='#dx1e1e', secondary='#2d2d2d', accent='#4caf50')
    ui.query('body').classes('bg-gray-900 text-white')
    
    # State
    state = {
        'positions': [],
        'accounts': [],
        'selected_account': None,
        'selected_account': None,
        'balance': {}
    }
    
    async def refresh_data():
        if not service.session:
            if not await service.login():
                ui.notify('Login failed! Check .env credentials.', type='negative')
                return

        if not state['accounts']:
            accs = await service.get_accounts()
            state['accounts'] = accs
            if accs:
                # Set default account description for dropdown
                state['selected_account'] = accs[0]

        # Fetch positions & balance
        try:
            state['balance'] = await service.get_balance(state['selected_account'])
            raw_rows = await service.get_positions(state['selected_account'])
            
            # Process for hybrid view (CC grouping)
            display_rows = service.get_dashboard_rows(raw_rows)
            state['positions'] = display_rows
            
            # Update UI
            content_container.refresh()
            ui.notify('Data refreshed', type='positive')
        except Exception as e:
            ui.notify(f'Error fetching data: {str(e)}', type='negative')

    # UI Layout
    with ui.column().classes('w-full max-w-7xl mx-auto p-4 gap-6'):
        
        # Header
        with ui.row().classes('w-full items-center justify-between mb-2'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('show_chart', size='lg').classes('text-red-500')
                ui.label('Tastytrade Holdings').classes('text-2xl font-bold tracking-tight')
            
            with ui.row().classes('gap-4'):
                ui.button('Refresh', icon='refresh', on_click=refresh_data).props('outline rounded text-color=white')

        @ui.refreshable
        def content_container():
            # Access state from closure
            positions = state['positions']
            bal = state['balance'] # Dict
            
            net_liq = bal.get('net_liq', 0.0)
            avail_bal = bal.get('equity_buying_power', 0.0)
            
            # Summary Metrics
            total_pl = sum(p['p_l'] for p in positions) if positions else 0.0
            total_cost = sum(p['cost_basis'] for p in positions) if positions else 0.0
            
            # Portfolio P/L % (Return on Account Basis)
            # Basis = Net Liq - Unrealized P/L (Proxy for Principal + Realized)
            account_basis = net_liq - total_pl
            portfolio_pl_pct = (total_pl / account_basis * 100) if account_basis > 0 else 0.0
            
            # Cash Utilization
            # Utilized = 1 - (Avail / Net Liq)
            cash_util_pct = ((1 - (avail_bal / net_liq)) * 100) if net_liq > 0 else 0.0
            
            with ui.grid(columns=6).classes('w-full gap-4 mb-6'):
                # 1. Net Liquidating Value
                with ui.card().classes('bg-gray-800 border-l-4 border-blue-500'):
                    ui.label('Net Liq').classes('text-gray-400 text-xs uppercase')
                    ui.label(format_currency(net_liq)).classes('text-2xl font-bold')
                
                # 2. Available Balance & Utilization
                with ui.card().classes('bg-gray-800 border-l-4 border-green-500'):
                    ui.label('Avail Balance').classes('text-gray-400 text-xs uppercase')
                    ui.label(format_currency(avail_bal)).classes('text-xl font-bold')
                    ui.label(f"{cash_util_pct:.1f}% Utilized").classes('text-xs text-gray-500')
                
                # 3. Unrealized P/L $
                with ui.card().classes('bg-gray-800 border-l-4 border-purple-500'):
                    ui.label('Unrealized P/L').classes('text-gray-400 text-xs uppercase')
                    ui.label(format_currency(total_pl)).classes(f'text-2xl font-bold {format_color(total_pl)}')
                    
                # 4. Portfolio P/L %
                with ui.card().classes('bg-gray-800 border-l-4 border-yellow-500'):
                    ui.label('Portfolio P/L %').classes('text-gray-400 text-xs uppercase')
                    ui.label(f"{portfolio_pl_pct:.2f}%").classes(f'text-2xl font-bold {format_color(portfolio_pl_pct)}')
                
                # 5. Total Positions
                with ui.card().classes('bg-gray-800 border-l-4 border-gray-500'):
                    ui.label('Positions').classes('text-gray-400 text-xs uppercase')
                    ui.label(str(len(positions) if positions else 0)).classes('text-2xl font-bold')

            # Flat Table with Hybrid Rows
            if not positions:
                return

            columns = [
                {'name': 'quantity', 'label': 'Qty', 'field': 'quantity', 'sortable': True, 'align': 'right'},
                {'name': 'symbol', 'label': 'Symbol', 'field': 'symbol', 'sortable': True, 'align': 'left'},
                {'name': 'type', 'label': 'Type', 'field': 'type', 'sortable': True, 'align': 'left'},
                {'name': 'avg_open_price', 'label': 'Avg Price', 'field': 'avg_open_price', 'sortable': True},
                {'name': 'current_price', 'label': 'Mark', 'field': 'current_price', 'sortable': True},
                {'name': 'p_l', 'label': 'P/L Open', 'field': 'p_l', 'sortable': True},
                {'name': 'p_l_percent', 'label': 'P/L %', 'field': 'p_l_percent', 'sortable': True},
            ]
            
            table = ui.table(columns=columns, rows=positions, pagination=10).classes('w-full bg-gray-800 text-white rounded-lg shadow-lg')
            
            # Formatting Slots
            for col in ['avg_open_price', 'current_price']:
                table.add_slot(f'body-cell-{col}', r'''
                    <q-td :key="props.col.name" :props="props">
                        <div v-if="props.row.is_composite" class="text-gray-500 italic">Mix</div>
                        <div v-else>
                            {{ props.value.toLocaleString('en-US', {style: 'currency', currency: 'USD'}) }}
                        </div>
                    </q-td>
                ''')
            
            # Color formatted columns
            for col in ['p_l', 'day_pl']:
                 table.add_slot(f'body-cell-{col}', r'''
                    <q-td :key="props.col.name" :props="props">
                        <div :class="props.value >= 0 ? 'text-green-400' : 'text-red-400'">
                            {{ props.value.toLocaleString('en-US', {style: 'currency', currency: 'USD'}) }}
                        </div>
                    </q-td>
                ''')

            table.add_slot('body-cell-p_l_percent', r'''
                <q-td key="p_l_percent" :props="props">
                    <div :class="props.row.p_l_percent >= 0 ? 'text-green-400' : 'text-red-400'">
                        {{ props.row.p_l_percent.toFixed(2) }}%
                    </div>
                </q-td>
            ''')


            
            # Symbol slot to highlight Composites
            table.add_slot('body-cell-symbol', r'''
                <q-td key="symbol" :props="props">
                    <div v-if="props.row.is_composite" class="font-bold text-blue-400">
                        {{ props.row.symbol }}
                        <q-tooltip>Covered Call Strategy</q-tooltip>
                    </div>
                    <div v-else>
                        {{ props.row.symbol }}
                    </div>
                </q-td>
            ''')

        content_container()

    # Initial data load
    await refresh_data()

ui.run(title='Tastytrade Viewer', dark=True, port=8080)
