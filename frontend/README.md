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
- The backend seeds 30 simulated European patients (about 50 screenings plus follow-ups) at startup, so every screen has data.
- `POST /api/samples/{id}/analyze` runs a demo image, which gives the sample tray a one-click action.

## Suggested screens (RetinaAI Nexus)

1. **Screen**: upload or pick from the sample tray, then show the case result: image with a heatmap
   toggle, probability bars, a triage badge and `triage.reason`. If quality failed, show the
   "retake" message with `quality.reason`.
2. **Triage queue** (`GET /api/queue`): sorted by urgency; open a case to review it
   (`PATCH /api/cases/{id}`).
3. **European Retina Passport**: a language picker (`GET /api/languages`) plus a button that opens
   `case.report_url + "?lang=xx"` in a new tab or iframe. "Share" calls `POST /api/cases/{id}/share`
   and shows `passport_url` (and/or a QR code).
4. **Follow-up dashboard**:
   - cards from `GET /api/dashboard` (attendance rate, overdue, missed, open referrals);
   - a per-country bar chart or map of Europe from `by_country`;
   - screenings per month from `monthly`;
   - a worklist from `GET /api/followups?open=true`, with actions *Book* (PATCH `appointment_at`),
     *Attended*, *Missed* and *Remind* (`POST /remind`, shows the translated SMS).
5. **Patient page** (`GET /api/patients/{ref}`): the screening timeline and follow-ups.

Always show the disclaimer: "Research prototype with simulated data. Not for clinical diagnosis."
