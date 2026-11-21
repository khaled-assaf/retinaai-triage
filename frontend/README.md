# Frontend — RetinaAI Nexus

React + TypeScript + Vite + Tailwind CSS. Talks to the FastAPI backend through the
Vite dev-server proxy (`/api` → `http://localhost:8000`), so no CORS setup is needed.

## Run

```bash
cd frontend
npm install        # first time only
npm run dev        # http://localhost:5173
```

Have the backend running on :8000 first (see root README). The navbar shows a pulsing
API dot when it is reachable.

Other scripts:

```bash
npm run typecheck  # tsc --noEmit
npm run build      # typecheck + production build to dist/
npm run smoke:pdf  # render passport PDFs headlessly (written to /tmp/opencode)
```

## Structure

```
src/
├── api/            client.ts (fetch wrapper + ApiError), cases.ts, samples.ts, followups.ts (fixture fallback)
├── types.ts        API types mirroring backend/app/schemas.py (keep in sync!)
├── i18n/passport.ts        Retina Passport report strings — EN/RO/DE/FR/ES
├── pdf/PassportDocument.tsx  client-side passport PDF (Noto Sans fonts in public/fonts)
├── hooks/          useHealth (navbar API dot)
├── utils/time.ts   timeAgo()
├── components/
│   ├── layout/     Navbar (pill nav, CTA, API dot)
│   ├── screening/  UploadCard (dropzone, validation, preview)
│   ├── case/       HeatmapViewer (Grad-CAM slider), TriageBadge, GradeScale,
│   │               ProbabilitiesBars, QualityPanel, RetakeCard, ReviewModal
│   ├── passport/   PassportPanel (language picker, preview, PDF download)
│   └── ui/         ToastProvider (useToast), Spinner
└── pages/          Landing, Screening, CaseResult, Queue, Followups
```

- API contract: [`../docs/API.md`](../docs/API.md)
- Image URLs from API responses are relative (`/api/...`) — use directly in `<img src>`
- Every backend error is `{"detail": "..."}` → surfaces as `ApiError.message` → toast it
