# Frontend

React, TypeScript, and Vite application. Requires Node.js 20+ and npm.

```powershell
Copy-Item .env.example .env
Set-Location frontend
npm install
npm run dev
```

Set `VITE_API_BASE_URL` when the API is hosted somewhere other than
`http://localhost:8000/api/v1`. Production build: `npm run build`.
The interface supports English and Tamil, but reviewed disease translations
must be added by an authorized administrator. Offline model inference and PWA
caching are not enabled.
