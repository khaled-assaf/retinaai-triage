# Frontend

**Frontend teammate: init Vite + React here.**

```bash
cd frontend
npm create vite@latest . -- --template react-ts   # or "react" for plain JS
npm install
npm run dev                                         # http://localhost:5173
```

## Proxy /api to the backend

Have the backend running on :8000 (see the root README), then edit `vite.config.ts`:

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
```

With the proxy you can call `fetch("/api/queue")` and use the relative image URLs from
responses (`/api/cases/c_0001/thumbnail`) directly in `<img src>`. CORS is also enabled
for :5173 and :3000 if you prefer calling `http://localhost:8000` directly.

## API

- Contract with examples: [`../docs/API.md`](../docs/API.md)
- Live docs (try requests in the browser): http://localhost:8000/docs
- The backend seeds 8 demo cases at startup, so `/api/queue` already has data.
- `POST /api/samples/{id}/analyze` runs a demo image, which gives the sample tray a one-click action.

Suggested screens: Upload/Sample tray → Case result (image, heatmap toggle, probabilities
bar chart, triage badge) → Queue dashboard (sorted by urgency) → Review form (PATCH).
Always show the disclaimer: "Research prototype. Not for clinical diagnosis."
