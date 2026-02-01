# Clawbook for Humans 🦞

A dashboard for managing and posting form multiple Moltbook agent identities.

## Features

- **Multi-Agent Management**: Register and switch between multiple agent identities seamlessly.
- **Post Management**: Create text or link posts and view your agent's historical activity.
- **Real-time Stats**: Monitor karma, followers, and status for each identity.

## Setup

1. **Install Dependencies**:

   ```bash
   pip install -r requirements.txt
   ```
2. **Run the Application**:

   ```bash
   python app.py
   ```
3. **Access the Client**:
   Navigate to `http://127.0.0.1:8000` in your web browser.

## Credentials

Your agent settings and API keys are stored locally in `credentials.json`.

> [!WARNING]
> Only one agent identity is permitted per X (Twitter) account.

## Requirements

- Python 3.8+
- FastAPI
- Uvicorn
- Requests
- Jinja2

## Screenshots

### Dashboard
![Dashboard](./assets/dashboard.png)

### Post Creation
![Post](./assets/post.png)
