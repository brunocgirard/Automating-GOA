# Next.js + FastAPI Deployment Guide

This project deploys as two services:

- `frontend/` to Vercel
- FastAPI backend (`api.main:app`) to Railway or Render

## 1) Backend Deployment (Railway/Render)

### Build Source

Backend deployment uses the root `Dockerfile`.

### Required Environment Variables

- `GEMINI_API_KEY`: Gemini API key for extraction.
- `GOOGLE_API_KEY`: Optional. If unset, backend maps it from `GEMINI_API_KEY`.
- `DATABASE_PATH`: SQLite file path inside container (example: `/data/crm_data.db`).
- `CORS_ORIGINS`: Comma-separated origins (example: `https://your-app.vercel.app`).

### Persistent Storage

If you keep SQLite in production, mount a persistent disk and point `DATABASE_PATH` to that mount path.

### Health Check

Use `GET /health` to verify runtime status.

## 2) Frontend Deployment (Vercel)

### Project Settings

- Root directory: `frontend`
- Framework preset: Next.js

### Required Environment Variables

- `NEXT_PUBLIC_API_URL=https://<your-backend-domain>`

### Production Check

After deploy, verify:

1. Dashboard loads quotes.
2. Upload endpoint works.
3. Processing wizard reaches extraction and generate steps.
4. Quote preview renders from backend report HTML.

## 3) CORS Setup Example

Set backend `CORS_ORIGINS` with your Vercel domain and local dev origins:

```env
CORS_ORIGINS=https://your-app.vercel.app,http://localhost:3000,http://127.0.0.1:3000
```
