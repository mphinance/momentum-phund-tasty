# Momentum Phund

> by **Momentum Phinance LLC**

A modern, real-time portfolio dashboard for tastytrade, built with NiceGUI.

📰 **[Read more on Substack](https://mphinance.substack.com)**

---

## Features

- 🚀 **Real-time positions** with live quote streaming via DXLink
- 📊 **P/L tracking** - Unrealized gains/losses with color-coded indicators
- 📈 **TradingView charts** - Click any row to view interactive charts
- 🔄 **Auto-refresh** - Toggle 60-second automatic data refresh
- 💓 **Session keep-alive** - Automatic heartbeat prevents token timeouts
- 🎯 **Covered Call grouping** - Hybrid view bundles equity + short calls
- 📱 **Mobile responsive** - Works great on phones and tablets
- 🌙 **Dark mode** - Beautiful gradient-themed dark interface

---

## Setup

### 1. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Credentials

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and add your tastytrade OAuth credentials:

```
TASTYTRADE_CLIENT_SECRET=your_client_secret_here
TASTYTRADE_REFRESH_TOKEN=your_refresh_token_here
```

> **Note:** You need to register an OAuth application in your tastytrade account settings to get these credentials.

---

## Running the App

```bash
./venv/bin/python main.py
```

Open your browser to `http://localhost:8080`

---

## Screenshots

The dashboard displays:
- Net Liquidating Value
- Buying Power & Utilization %
- Unrealized P/L ($ and %)
- Position count
- Live positions table with click-to-chart

---

## Tech Stack

- **[NiceGUI](https://nicegui.io/)** - Python-based web UI framework
- **[tastytrade SDK](https://github.com/tastyware/tastytrade)** - Official API wrapper
- **[TradingView Widget](https://www.tradingview.com/widget/)** - Interactive charts
- **DXLink** - Real-time quote streaming

---

## License

MIT
