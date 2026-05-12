# RankPulse 🚀

Instant SEO audits for e-commerce stores. Catch broken meta tags, slow pages, and missing schema before Google does.

## Quick Start

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Test
```bash
curl -X POST http://localhost:8001/api/audit \
  -H "Content-Type: application/json" \
  -d '{"url": "https://yourstore.com"}'
```

## Architecture

- **Backend:** FastAPI (Python) with 6 SEO analyzers
- **Frontend:** Next.js 14 + Tailwind CSS
- **Scoring:** Weighted 0-100 (meta 30%, images 20%, technical 20%, schema 15%, headings 15%)

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API info |
| `/health` | GET | Health check |
| `/api/audit` | POST | Full SEO audit |
| `/api/quick-check` | POST | Fast meta + heading check |

## Deploy

### Railway (Backend)
1. Connect GitHub repo
2. Set root directory to `backend`
3. Add env vars if needed
4. Deploy

### Vercel (Frontend)
1. Connect GitHub repo
2. Set root directory to `frontend`
3. Add env var: `NEXT_PUBLIC_API_URL` = your Railway backend URL
4. Deploy

## License
MIT