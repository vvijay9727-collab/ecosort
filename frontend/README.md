# EcoSort frontend

Install dependencies and start the Vite development server from this directory
in PowerShell:

```powershell
npm.cmd install
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

The local API base URL defaults to `http://127.0.0.1:8000`. Override it with
`VITE_API_BASE_URL` before starting Vite if the FastAPI server uses another
address. Authentication is handled with an HTTP-only cookie; do not place
passwords or authentication secrets in frontend environment variables.

Citizen registration and login are available at `/user/register` and
`/user/login`. Provisioned authorities sign in at `/authority/login`. The
frontend build and lint commands are `npm.cmd run build` and `npm.cmd run lint`.
