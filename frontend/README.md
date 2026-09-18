# Cascade site

Vite + React + TypeScript + Tailwind. Marketing, docs, and the GitHub-sign-in dashboard.

```bash
npm install
npm run dev
```

Open http://localhost:5173. Sign-in and `/api/*` proxy to `uvicorn api.server:app` on port 8000. For a local session without OAuth secrets, set `CASCADE_DEV_LOGIN=1` on the API.
