# Cascade frontend

Vite + React + TypeScript + Tailwind migration console.

```bash
# From repo root — API must be running on :8000
uvicorn api.server:app --reload --port 8000

# Then:
npm install
npm run dev
```

Calls `/api/*` only (proxied to FastAPI). Fixture path is the default; no secrets in the client.
