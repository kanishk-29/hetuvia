# HETUVIA frontend

Minimal Next.js 16.4.6 / React 19.3.0 health-status page for the HETUVIA prototype.

## Current scope

- Displays the result of `GET http://localhost:8000/api/v1/health`.
- Override the API base URL with `NEXT_PUBLIC_API_URL` if it is not on port 8000.
- No clinical workflows live here. The interactive prototype is the static demo at [`../docs/demo/index.html`](../docs/demo/index.html).

## Commands

```powershell
npm install
npm run dev     # http://localhost:3000
npm run build
npm run lint
```

## Contributor note

Follow [`AGENTS.md`](AGENTS.md) in this folder. When writing frontend code, first read the relevant Next.js 16.4.6 guides under `node_modules/next/dist/docs/`.

The HTTP interface is specified in [`../docs/srs.md`](../docs/srs.md) section 7.2. Clinical API endpoints are currently out of scope.
