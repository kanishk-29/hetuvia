# HETUVIA frontend

Next.js 16.4.6 / React 19.3.0 read-only operator console for the HETUVIA prototype.

## Current scope

- Calls the backend operator API (`/api/v1/summary`, `/people`, `/care-gap-findings`, `/data-quality-findings`, `/recommendations`, `/audit-events`) and renders summary counts, work queue, people, findings and audit history.
- Uses `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).
- Read-only: no review, import or reset actions live here. Those workflows remain CLI-only until authentication and authorisation exist.
- The interactive scripted demo remains at [`../docs/demo/index.html`](../docs/demo/index.html).

## Commands

```powershell
npm install
npm run dev     # http://localhost:3000
npm run build
npm run lint
```

## Contributor note

Follow [`AGENTS.md`](AGENTS.md) in this folder. When writing frontend code, first read the relevant Next.js 16.4.6 guides under `node_modules/next/dist/docs/`.

The HTTP interface is specified in [`../docs/api_contract.md`](../docs/api_contract.md) and [`../docs/srs.md`](../docs/srs.md) section 7.2.
