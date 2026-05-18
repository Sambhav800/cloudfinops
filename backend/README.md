# CloudFinOps Python Backend

High-performance Python backend for AI-driven cloud cost optimization.

## Setup

1. Create virtual environment:
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate  # Windows
# or
source venv/bin/activate  # Mac/Linux
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
- Copy `.env` and update values if needed
- Ensure credentials match the frontend `.env.local`

4. Start the server:
```bash
uvicorn app.main:app --reload --port 8000
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/integrations` | List cloud integrations |
| GET | `/api/resources` | Get scanned resources |
| GET | `/api/stats` | Dashboard statistics |
| POST | `/api/scan` | Trigger background scan |
| GET | `/api/notifications` | Get AI notifications |
| WS | `/ws/{user_id}` | Real-time updates |

## Architecture

```
backend/
├── app/
│   ├── main.py         # FastAPI entry point
│   ├── config.py       # Settings
│   ├── auth/           # Clerk JWT verification
│   ├── api/            # Routes & WebSocket
│   ├── db/             # MongoDB client
│   ├── scanners/       # AWS/Azure/GCP scanners
│   └── security/       # Crypto utilities
└── requirements.txt
```

## Testing

```bash
# Health check
curl http://localhost:8000/api/health

# With auth (replace TOKEN)
curl -H "Authorization: Bearer TOKEN" http://localhost:8000/api/integrations
```
