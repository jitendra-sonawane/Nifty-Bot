# Upstox Trading Bot

This is an automated trading bot for Nifty 50 options using the Upstox API.

## Setup

First, navigate to the backend directory:
```bash
cd backend
```

1.  **Install Python**: Ensure Python 3.8+ is installed.
2.  **Install `uv`**: `uv` is a fast Python package installer.
    ```bash
    pip install uv
    ```
3.  **Create a virtual environment (optional but recommended)**:
    ```bash
    uv venv
    ```
    Activate the environment:
    ```bash
    source .venv/bin/activate
    ```
4.  **Install Dependencies**:
    ```bash
    uv sync
    ```
5.  **Configure Credentials**:
    *   Rename `.env.example` to `.env`.
    *   Open `.env` and add your Upstox API Key, Secret, and Redirect URI.

## Running the Bot

From the `backend` directory, run the main script:
```bash
python3 main.py
```

## First Run
On the first run, the bot will ask you to login:
1.  It will print a Login URL.
2.  Open the URL in your browser and login to Upstox.
3.  After login, you will be redirected to your Redirect URI.
4.  Copy the `code` parameter from the URL (e.g., `?code=xxxxxx`).
5.  Paste the code into the terminal.
6.  The bot will generate an Access Token and print it. **Save this token in your `.env` file** to avoid logging in every time.

## Strategy
The bot uses a 5-minute timeframe strategy:
*   **Buy Call**: Close > 5 EMA, 5 EMA > 20 EMA, RSI > 55.
*   **Buy Put**: Close < 5 EMA, 5 EMA < 20 EMA, RSI < 45.

## Documentation

📚 For detailed documentation, guides, and architecture details, see the **[docs/](docs/)** directory:
- **Setup & Guides**: [docs/guides/](docs/guides/)
- **Features**: [docs/features/](docs/features/)
- **Architecture**: [docs/architecture/](docs/architecture/)
- **Backend Docs**: [docs/backend/](docs/backend/)
- **Fixes & Troubleshooting**: [docs/fixes/](docs/fixes/)

See [docs/README.md](docs/README.md) for the complete documentation index.
