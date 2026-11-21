/**
 * Passport PDF smoke test (Node): renders real PassportDocument instances and
 * writes PDFs to /tmp/opencode. Run the bundled output with the dev server's
 * public/ as cwd, i.e. from frontend/:  node /tmp/opencode/smoke-pdf.mjs
 */
import { writeFileSync } from "node:fs";
import QRCode from "qrcode";
import { PassportDocument } from "../src/pdf/PassportDocument.tsx";
import type { Case } from "../src/types.ts";

const goodCase: Case = {
  case_id: "c_smoke1",
  created_at: new Date().toISOString(),
  patient_ref: "DEMO-007",
  quality: {
    passed: true,
    score: 0.82,
    reason: "OK",
    checks: { blur: 0.82, exposure: "ok", framing: "ok" },
  },
  prediction: {
    grade: 3,
    label: "Severe NPDR",
    confidence: 0.71,
    probabilities: [0.02, 0.05, 0.17, 0.71, 0.05],
  },
  heatmap_url: "/api/cases/c_smoke1/heatmap",
  image_url: "/api/cases/c_smoke1/image",
  triage: {
    level: "urgent",
    label: "Urgent referral",
    action: "Refer to an ophthalmologist",
  },
  review: { status: "pending", clinician_grade: null, note: null },
  model_version: "mock-v0",
  processing_ms: 412,
  disclaimer: "Research prototype. Not for clinical diagnosis.",
};

const uncertainCase: Case = {
  ...goodCase,
  case_id: "c_smoke2",
  prediction: {
    grade: 1,
    label: "Mild NPDR",
    confidence: 0.55,
    probabilities: [0.4, 0.55, 0.03, 0.01, 0.01],
  },
  triage: {
    level: "review",
    label: "Needs clinician review",
    action: "Low-confidence prediction — verify clinically",
  },
};

const retakeCase: Case = {
  ...goodCase,
  case_id: "c_smoke3",
  prediction: null,
  heatmap_url: null,
  quality: {
    passed: false,
    score: 0.0,
    reason: "Image is blurry",
    checks: { blur: 0.12, exposure: "ok", framing: "ok" },
  },
  triage: {
    level: "retake",
    label: "Retake image",
    action: "Recapture the fundus photo (check focus, lighting and centering)",
  },
};

async function render(mod: typeof import("@react-pdf/renderer"), doc: React.ReactElement, out: string) {
  const buf = mod.renderToBuffer
    ? await mod.renderToBuffer(doc)
    : Buffer.from(await (await mod.pdf(doc).toBlob()).arrayBuffer());
  writeFileSync(out, buf);
  console.log("wrote", out, buf.length, "bytes, magic:", buf.subarray(0, 5).toString());
}

const qr = await QRCode.toDataURL("http://localhost:5173/case/c_smoke1", {
  margin: 1,
  width: 160,
});

const mod = (await import("@react-pdf/renderer")) as typeof import("@react-pdf/renderer");
await render(mod, <PassportDocument caseData={goodCase} lang="en" qrDataUrl={qr} />, "/tmp/opencode/passport-en.pdf");
await render(mod, <PassportDocument caseData={goodCase} lang="ro" qrDataUrl={qr} />, "/tmp/opencode/passport-ro.pdf");
await render(mod, <PassportDocument caseData={uncertainCase} lang="de" qrDataUrl={qr} />, "/tmp/opencode/passport-de.pdf");
await render(mod, <PassportDocument caseData={retakeCase} lang="en" qrDataUrl={qr} />, "/tmp/opencode/passport-retake.pdf");
console.log("OK: 4 PDFs rendered");
