# GOA Frontend (Next.js)

## Local Development

1. Create env file:

```bash
cp .env.example .env.local
```

2. Set API URL in `.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

3. Start dev server:

```bash
npm install
npm run dev
```

Frontend runs on `http://localhost:3000`.

## Build Checks

```bash
npm run lint
npm run build
```

## Deployment (Vercel)

- Set project root to `frontend/`
- Set `NEXT_PUBLIC_API_URL` to your deployed backend URL
