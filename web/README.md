# Catan Coach browser app

Adapted from the Catanatron UI at commit
`ecf931181b9a65bb4116a2153fb78c16f1438e00`. Catan Coach owns this copy while Catanatron
remains the pinned game engine.

Requires Node.js 24 and npm 11.

```bash
npm ci
npm test -- --run
npm run build
```

`npm run start` runs the Vite development server on port 3000 and proxies `/api` to a
Catan Coach server on port 5001.
