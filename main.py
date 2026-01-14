from nicegui import ui, app
from services.tastytrade_api import TastytradeService
from dotenv import load_dotenv
import asyncio
from collections import defaultdict
from datetime import datetime

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
        'balance': {},
        'last_refresh': None,
        'last_keepalive': None,
        'auto_refresh': False
    }
    
    async def refresh_data(silent=False):
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
            state['last_refresh'] = datetime.now()
            
            # Update UI
            content_container.refresh()
            status_bar.refresh()
            if not silent:
                ui.notify('Data refreshed', type='positive')
        except Exception as e:
            ui.notify(f'Error fetching data: {str(e)}', type='negative')

    # UI Layout
    # Custom CSS for Gradient Text + Mobile Responsiveness
    ui.add_head_html('''
        <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
        <style>
        .gradient-text {
            background: linear-gradient(90deg, #00d4ff, #9c40ff, #ff6b6b);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
            animation: pulse 2s infinite;
        }
        .status-dot.active { background: #4ade80; }
        .status-dot.inactive { background: #f87171; }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        /* Mobile Responsiveness */
        @media (max-width: 768px) {
            .header-title { font-size: 1.25rem !important; }
            .header-subtitle { font-size: 0.7rem !important; }
            .metric-card { padding: 0.5rem !important; }
            .metric-label { font-size: 0.6rem !important; }
            .metric-value { font-size: 1rem !important; }
            .status-bar { flex-wrap: wrap; gap: 0.5rem !important; padding: 0.5rem !important; }
            .status-item { font-size: 0.7rem !important; }
            .q-table { font-size: 0.75rem !important; }
            .q-table th, .q-table td { padding: 4px 8px !important; }
        }
        @media (max-width: 480px) {
            .header-title { font-size: 1rem !important; }
            .metric-grid { grid-template-columns: repeat(2, 1fr) !important; }
            .hide-mobile { display: none !important; }
        }
        
        /* Changelog drawer styles */
        .changelog-item {
            border-left: 3px solid #4ade80;
            padding-left: 12px;
            margin-bottom: 12px;
        }
        .changelog-date {
            color: #9ca3af;
            font-size: 0.75rem;
        }
        .changelog-text {
            color: #e5e7eb;
            font-size: 0.875rem;
        }
        </style>
    ''')
    
    # Chart Dialog Functionality
    chart_container = None # Placeholder for current chart container
    
    def open_chart(e):
        # Handle NiceGUI event arguments
        # e is GenericEventArguments, e.args = [evt, row, index]
        row_data = None
        if hasattr(e, 'args') and len(e.args) >= 2:
            row_data = e.args[1]
        elif isinstance(e, dict):
            row_data = e
            
        if not row_data:
            return

        # Extract symbol
        # If composite (CC), parse the underlying: "AMD (CC)" -> "AMD"
        symbol = row_data.get('symbol', 'SPY')
        if '(CC)' in symbol:
            symbol = symbol.split(' ')[0]
            
        print(f"Opening chart for {symbol}")
        
        if chart_dialog:
            # Set container HTML first
            chart_html.content = f'<div id="tradingview_{symbol}" style="height: 100%; width: 100%;"></div>'
            chart_dialog.open()
            
            # Initialize widget via JS after dialog opens
            ui.run_javascript(f'''
              new TradingView.widget(
              {{
                "autosize": true,
                "symbol": "{symbol}",
                "interval": "D",
                "timezone": "Etc/UTC",
                "theme": "dark",
                "style": "1",
                "locale": "en",
                "toolbar_bg": "#1f2937",
                "enable_publishing": false,
                "hide_side_toolbar": false,
                "allow_symbol_change": true,
                "container_id": "tradingview_{symbol}",
                "width": "100%",
                "height": "100%"
              }}
              );
            ''')

    # Create the dialog once
    with ui.dialog().classes('w-full max-w-4xl') as chart_dialog:
        with ui.card().classes('w-full h-[600px] bg-gray-900 p-0 overflow-hidden relative'):
             # Close button overlay
            ui.button(icon='close', on_click=chart_dialog.close).props('flat round dense text-color=white').classes('absolute top-2 right-2 z-50 bg-gray-800/50')
            
            # Chart Container
            chart_html = ui.html('', sanitize=False).classes('w-full h-full')
    
    # Changelog Drawer
    with ui.right_drawer(value=False).classes('bg-gray-800 w-80') as changelog_drawer:
        with ui.column().classes('p-4 gap-4'):
            with ui.row().classes('items-center justify-between w-full'):
                ui.label('📋 Changelog').classes('text-xl font-bold text-white')
                ui.button(icon='close', on_click=lambda: changelog_drawer.set_value(False)).props('flat round text-color=white')
            
            ui.separator().classes('bg-gray-600')
            
            # Changelog entries - most recent first
            changelog_entries = [
                ('Jan 14, 2025', 'Added TradingView charts - click any row to view'),
                ('Jan 14, 2025', 'Added auto-refresh toggle for live price updates every 60 seconds'),
                ('Jan 14, 2025', 'Added session keep-alive heartbeat to prevent token timeouts'),
                ('Jan 14, 2025', 'Added status bar showing last refresh time, session status, and heartbeat'),
                ('Jan 14, 2025', 'Added changelog sidebar and mobile-responsive design'),
                ('Jan 13, 2025', 'Discord webhook integration for scanner results'),
                ('Jan 13, 2025', 'Google Sheets export via webhooks'),
                ('Jan 11, 2025', 'Hybrid Covered Call grouping in portfolio view'),
                ('Jan 11, 2025', 'Real-time P/L with red/green indicators'),
            ]
            
            with ui.scroll_area().classes('h-full'):
                for date, text in changelog_entries:
                    with ui.column().classes('changelog-item'):
                        ui.label(date).classes('changelog-date')
                        ui.label(text).classes('changelog-text')

    with ui.column().classes('w-full max-w-7xl mx-auto p-4 gap-4'):
        
        # Header
        with ui.row().classes('w-full items-center justify-between mb-2 flex-wrap gap-2'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('rocket_launch', size='lg').classes('text-blue-400 hide-mobile')
                with ui.column().classes('gap-0'):
                    ui.label('Momentum Phund').classes('text-3xl font-black tracking-tight gradient-text header-title')
                    ui.label('by Momentum Phinance LLC').classes('text-xs text-gray-500')
                    ui.label('Tastytrade Portfolio Holdings').classes('text-sm text-gray-400 header-subtitle')
            
            with ui.row().classes('gap-2 items-center'):
                ui.link(target='https://mphinance.substack.com', new_tab=True).classes('no-underline').add_slot('default', '''
                    <q-btn icon="article" label="Substack" rounded dense color="orange" text-color="white" class="shadow-lg" />
                ''')
                ui.button('Refresh', icon='refresh', on_click=refresh_data).props('outline rounded text-color=white dense')
                ui.button(icon='update', on_click=lambda: changelog_drawer.set_value(True)).props('outline rounded text-color=white dense').tooltip('View Changelog')
        
        # Status Bar
        @ui.refreshable
        def status_bar():
            with ui.row().classes('w-full items-center justify-between bg-gray-800 rounded-lg px-4 py-2 text-sm status-bar'):
                # Left side: Session status & last refresh
                with ui.row().classes('items-center gap-4 flex-wrap'):
                    # Session indicator
                    with ui.row().classes('items-center gap-2 status-item'):
                        if service.session:
                            ui.html('<span class="status-dot active"></span>', sanitize=False)
                            ui.label('Active').classes('text-green-400')
                        else:
                            ui.html('<span class="status-dot inactive"></span>', sanitize=False)
                            ui.label('Inactive').classes('text-red-400')
                    
                    # Last refresh time
                    with ui.row().classes('items-center gap-1 status-item'):
                        ui.icon('schedule', size='xs').classes('text-gray-400')
                        if state['last_refresh']:
                            time_str = state['last_refresh'].strftime('%I:%M %p')
                            ui.label(time_str).classes('text-gray-300')
                        else:
                            ui.label('--').classes('text-gray-500')
                    
                    # Last keep-alive (hide on small mobile)
                    with ui.row().classes('items-center gap-1 status-item hide-mobile'):
                        ui.icon('favorite', size='xs').classes('text-gray-400')
                        if state['last_keepalive']:
                            time_str = state['last_keepalive'].strftime('%I:%M %p')
                            ui.label(time_str).classes('text-gray-300')
                        else:
                            ui.label('--').classes('text-gray-500')
                
                # Right side: Auto-refresh toggle
                with ui.row().classes('items-center gap-2'):
                    ui.label('Auto-Refresh (60s)').classes('text-gray-400')
                    
                    def toggle_auto_refresh(e):
                        state['auto_refresh'] = e.value
                    
                    ui.switch(value=state['auto_refresh'], on_change=toggle_auto_refresh).props('color=green')
        
        status_bar()

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
            
            with ui.grid(columns=5).classes('w-full gap-2 mb-4 metric-grid'):
                # 1. Net Liquidating Value
                with ui.card().classes('bg-gray-800 border-l-4 border-blue-500 metric-card'):
                    ui.label('Net Liq').classes('text-gray-400 text-xs uppercase metric-label')
                    ui.label(format_currency(net_liq)).classes('text-xl font-bold metric-value')
                
                # 2. Available Balance & Utilization
                with ui.card().classes('bg-gray-800 border-l-4 border-green-500 metric-card'):
                    ui.label('Buying Power').classes('text-gray-400 text-xs uppercase metric-label')
                    ui.label(format_currency(avail_bal)).classes('text-xl font-bold metric-value')
                    ui.label(f"{cash_util_pct:.0f}% Used").classes('text-xs text-gray-500')
                
                # 3. Unrealized P/L $
                with ui.card().classes('bg-gray-800 border-l-4 border-purple-500 metric-card'):
                    ui.label('P/L').classes('text-gray-400 text-xs uppercase metric-label')
                    ui.label(format_currency(total_pl)).classes(f'text-xl font-bold metric-value {format_color(total_pl)}')
                    
                # 4. Portfolio P/L %
                with ui.card().classes('bg-gray-800 border-l-4 border-yellow-500 metric-card'):
                    ui.label('Return').classes('text-gray-400 text-xs uppercase metric-label')
                    ui.label(f"{portfolio_pl_pct:.2f}%").classes(f'text-xl font-bold metric-value {format_color(portfolio_pl_pct)}')
                
                # 5. Total Positions
                with ui.card().classes('bg-gray-800 border-l-4 border-gray-500 metric-card'):
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
            
            table = ui.table(columns=columns, rows=positions, pagination=10).classes('w-full bg-gray-800 text-white rounded-lg shadow-lg cursor-pointer')
            table.on('rowClick', open_chart) 
            
            # Formatting Slots
            for col in ['avg_open_price', 'current_price']:
                table.add_slot(f'body-cell-{col}', r'''
                    <q-td :key="props.col.name" :props="props">
                        <div v-if="props.row.is_composite" class="text-gray-500 italic">Mix</div>
                        <div v-else>
                            {{ Number(props.value).toLocaleString('en-US', {style: 'currency', currency: 'USD'}) }}
                        </div>
                    </q-td>
                ''')
            
            # Color formatted columns (P/L)
            for col in ['p_l']:
                 table.add_slot(f'body-cell-{col}', r'''
                    <q-td :key="props.col.name" :props="props">
                        <div :class="props.value >= 0 ? 'text-green-400' : 'text-red-400'">
                            {{ Number(props.value).toLocaleString('en-US', {style: 'currency', currency: 'USD', signDisplay: 'always'}) }}
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

        # Background keep-alive timer (every 4 minutes)
        # This prevents the tastytrade session from timing out
        async def background_keep_alive():
            if service.session:
                success = await service.keep_alive()
                if success:
                    state['last_keepalive'] = datetime.now()
                    status_bar.refresh()
        
        ui.timer(240, background_keep_alive)  # 240 seconds = 4 minutes
        
        # Auto-refresh timer (every 60 seconds when enabled)
        async def auto_refresh_tick():
            if state['auto_refresh'] and service.session:
                await refresh_data(silent=True)
        
        ui.timer(60, auto_refresh_tick)  # Check every 60 seconds

    # Initial data load
    await refresh_data()

ui.run(title='Momentum Phinance LLC', dark=True, port=8080)
