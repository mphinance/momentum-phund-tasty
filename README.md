# Tastytrade Holdings Viewer

A modern dashboard for viewing your tastytrade positions, built with NiceGUI.

## Setup

1.  **Install Dependencies**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

2.  **Configure Credentials**
    Copy the example environment file:
    ```bash
    cp .env.example .env
    ```
    
    Edit `.env` and add your tastytrade API credentials:
    - `TASTYTRADE_CLIENT_SECRET`
    - `TASTYTRADE_REFRESH_TOKEN`
    
    *Note: You need to register an OAuth application in your tastytrade account settings to get these credentials.*

## Running the App

```bash
./venv/bin/python main.py
```

Open your browser to `http://localhost:8080`.

## Features
- Real-time positions view
- P/L tracking (unrealized)
- Account switching
- Dark mode interface
