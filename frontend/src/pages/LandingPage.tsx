import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  CalendarClock,
  Eye,
  FileCheck2,
  Languages,
  Loader2,
  Lock,
  ScanEye,
  ShieldAlert,
  ShieldCheck,
  Siren,
  Sparkles,
  Upload,
  UserCheck,
  type LucideIcon,
} from "lucide-react";
import { analyzeSample, getSamples } from "../api/samples";
import type { Sample } from "../types";
import { useToast } from "../components/ui/ToastProvider";

/* ---------------------------------- hero ----------------------------------- */

function Hero() {
  return (
    <section className="relative pt-10 pb-8 lg:pt-14">
      <div className="grid items-center gap-12 lg:grid-cols-12">
        {/* Left Column: Value Prop & CTAs */}
        <div className="text-center lg:col-span-6 lg:text-left">
          <p className="inline-flex items-center gap-2 rounded-full bg-teal-50/90 px-3.5 py-1.5 text-xs font-medium text-teal-800 ring-1 ring-teal-200/80 backdrop-blur-xs">
            <span className="size-1.5 rounded-full bg-teal-600" />
            AI-powered retinal screening · built for Europe
          </p>

          <h1 className="mt-6 font-display text-4xl leading-[1.08] font-medium tracking-tight text-slate-900 sm:text-5xl">
            One retinal photo.
            <br />A complete <em className="text-teal-700">path to care</em>.
          </h1>

          <p className="mx-auto mt-5 max-w-xl text-[15px] leading-relaxed text-slate-600 lg:mx-0">
            RetinaAI Nexus detects diabetic retinopathy in seconds, grades severity 0–4, and
            stays with the patient from referral to follow-up — with shareable multilingual
            reports.
          </p>

          <div className="mt-8 flex flex-wrap items-center justify-center gap-3 lg:justify-start">
            <Link
              to="/screening"
              className="group inline-flex items-center gap-2 rounded-full bg-teal-700 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-teal-900/15 transition hover:bg-teal-800"
            >
              Start screening
              <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
            <Link
              to="/queue"
              className="inline-flex items-center rounded-full bg-white/90 px-6 py-3 text-sm font-semibold text-slate-700 shadow-xs ring-1 ring-slate-200 transition hover:border-teal-300 hover:text-teal-800"
            >
              See the triage queue
            </Link>
          </div>

          <div className="mt-7 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-[11px] font-medium text-slate-500 lg:justify-start">
            <span className="flex items-center gap-1.5">
              <ShieldCheck className="size-3.5 text-teal-600" /> Quality-gated pipeline
            </span>
            <span className="flex items-center gap-1.5">
              <Activity className="size-3.5 text-teal-600" /> Grad-CAM explainability
            </span>
            <span className="flex items-center gap-1.5">
              <Languages className="size-3.5 text-teal-600" /> Reports in 5 languages
            </span>
          </div>
        </div>

        {/* Right Column: Connected Clinical Workflow Card */}
        <div className="lg:col-span-6">
          <div className="mx-auto max-w-lg rounded-3xl bg-white/80 p-5 shadow-xl shadow-slate-300/50 ring-1 ring-slate-200/90 backdrop-blur-sm sm:p-6">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3.5">
              <div>
                <p className="text-xs font-semibold text-slate-900">Clinical Care Pathway</p>
                <p className="text-[11px] text-slate-500">
                  End-to-end patient journey across RetinaAI Nexus
                </p>
              </div>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-teal-50 px-2.5 py-1 text-[11px] font-medium text-teal-700 ring-1 ring-teal-200/70">
                <span className="size-1.5 rounded-full bg-teal-600" />
                3 Integrated Modules
              </span>
            </div>

            <div className="mt-4 space-y-3">
              {/* Step 1 -> /screening */}
              <Link
                to="/screening"
                className="group flex items-start justify-between gap-3 rounded-2xl bg-slate-50/80 p-4 ring-1 ring-slate-200/80 transition hover:bg-teal-50/50 hover:ring-teal-300"
              >
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-xl bg-teal-700 text-white">
                    <ScanEye className="size-4.5" />
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-slate-900 group-hover:text-teal-800">
                      1. AI Screening &amp; Quality Gate
                    </p>
                    <p className="mt-0.5 text-xs leading-relaxed text-slate-500">
                      Validates scan clarity, grades diabetic retinopathy 0–4, and generates
                      Grad-CAM pathology heatmaps.
                    </p>
                  </div>
                </div>
                <ArrowRight className="mt-1 size-4 shrink-0 text-slate-400 transition-transform group-hover:translate-x-0.5 group-hover:text-teal-700" />
              </Link>

              {/* Step 2 -> /queue */}
              <Link
                to="/queue"
                className="group flex items-start justify-between gap-3 rounded-2xl bg-slate-50/80 p-4 ring-1 ring-slate-200/80 transition hover:bg-teal-50/50 hover:ring-teal-300"
              >
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-xl bg-amber-500/15 text-amber-700 ring-1 ring-amber-300/70">
                    <Siren className="size-4.5" />
                  </span>
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-semibold text-slate-900 group-hover:text-teal-800">
                        2. Priority Triage Queue
                      </p>
                      <span className="rounded-full bg-orange-100 px-2 py-0.5 text-[10px] font-semibold text-orange-800">
                        Urgent First
                      </span>
                    </div>
                    <p className="mt-0.5 text-xs leading-relaxed text-slate-500">
                      Automatically ranks referable and proliferative cases so specialists
                      review high-risk patients first.
                    </p>
                  </div>
                </div>
                <ArrowRight className="mt-1 size-4 shrink-0 text-slate-400 transition-transform group-hover:translate-x-0.5 group-hover:text-teal-700" />
              </Link>

              {/* Step 3 -> /followups */}
              <Link
                to="/followups"
                className="group flex items-start justify-between gap-3 rounded-2xl bg-slate-50/80 p-4 ring-1 ring-slate-200/80 transition hover:bg-teal-50/50 hover:ring-teal-300"
              >
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-xl bg-teal-50 text-teal-700 ring-1 ring-teal-200/80">
                    <CalendarClock className="size-4.5" />
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-slate-900 group-hover:text-teal-800">
                      3. Follow-ups &amp; Retina Passport
                    </p>
                    <p className="mt-0.5 text-xs leading-relaxed text-slate-500">
                      Tracks specialist referrals to completion and exports multilingual clinical
                      reports in 5 languages.
                    </p>
                  </div>
                </div>
                <ArrowRight className="mt-1 size-4 shrink-0 text-slate-400 transition-transform group-hover:translate-x-0.5 group-hover:text-teal-700" />
              </Link>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ----------------------------- clinical impact ----------------------------- */

const IMPACT_STATS = [
  {
    value: "1 in 3",
    label: "People with diabetes",
    detail: "Develop some form of diabetic retinopathy during their lifetime.",
  },
  {
    value: "90%+",
    label: "Preventable vision loss",
    detail: "Avoidable when retinal changes are caught early and referred on time.",
  },
  {
    value: "< 5 sec",
    label: "Time to triage decision",
    detail: "Automated quality check, 0–4 grading, and visual heatmap generation.",
  },
];

function ClinicalImpact() {
  return (
    <section className="mt-12">
      <div className="grid gap-4 rounded-2xl bg-gradient-to-r from-teal-50/80 via-white to-teal-50/80 p-6 shadow-xs ring-1 ring-teal-200/70 sm:p-8 md:grid-cols-3">
        {IMPACT_STATS.map(({ value, label, detail }) => (
          <div
            key={label}
            className="border-teal-200/60 last:border-none last:pr-0 md:border-r md:pr-6"
          >
            <p className="font-display text-3xl font-medium tracking-tight text-teal-700">
              {value}
            </p>
            <p className="mt-1 text-sm font-semibold text-slate-900">{label}</p>
            <p className="mt-1 text-xs leading-relaxed text-slate-600">{detail}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ------------------------------ live demo strip ---------------------------- */

function DemoStrip() {
  const [samples, setSamples] = useState<Sample[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const navigate = useNavigate();
  const { push } = useToast();

  useEffect(() => {
    getSamples().then(setSamples).catch(() => setSamples([]));
  }, []);

  async function run(s: Sample) {
    setBusyId(s.id);
    try {
      const c = await analyzeSample(s.id);
      navigate(`/case/${c.case_id}`);
    } catch (e) {
      push(e instanceof Error ? e.message : "Analysis failed", "error");
    } finally {
      setBusyId(null);
    }
  }

  if (samples.length === 0) return null;

  return (
    <section id="try" className="mt-12">
      <p className="text-center text-[11px] font-semibold tracking-widest text-slate-400 uppercase">
        Live demo — pick a retina, get a full case
      </p>
      <div className="mt-4 flex flex-wrap justify-center gap-3">
        {samples.map((s) => (
          <button
            key={s.id}
            type="button"
            title={s.label}
            onClick={() => void run(s)}
            disabled={busyId !== null}
            className="group relative overflow-hidden rounded-2xl shadow-xs ring-1 ring-slate-200 transition-all hover:-translate-y-0.5 hover:shadow-lg hover:shadow-teal-500/10 hover:ring-teal-400 disabled:opacity-60"
          >
            <img
              src={s.image_url}
              alt={s.label}
              className="h-24 w-36 object-cover transition-transform duration-300 group-hover:scale-105"
            />
            {busyId === s.id && (
              <span className="absolute inset-0 grid place-items-center bg-white/70 backdrop-blur-[2px]">
                <Loader2 className="size-5 animate-spin text-teal-700" />
              </span>
            )}
          </button>
        ))}
      </div>
    </section>
  );
}

/* -------------------------------- features --------------------------------- */

interface Feature {
  icon: LucideIcon;
  title: string;
  text: string;
  span: string;
  badge?: string;
  accent?: boolean;
}

const FEATURES: Feature[] = [
  {
    icon: ScanEye,
    title: "AI screening with Grad-CAM",
    text: "Upload a fundus photo and get a 0–4 severity grade in seconds — with a visual heatmap showing exactly where the model looked.",
    span: "md:col-span-3",
    badge: "Grades 0–4 · Explainable AI",
    accent: true,
  },
  {
    icon: Languages,
    title: "European Retina Passport",
    text: "Multilingual, shareable PDF reports: the exact same clinical findings, readable by any ophthalmologist across Europe.",
    span: "md:col-span-3",
    badge: "EN · RO · DE · FR · ES",
  },
  {
    icon: ShieldCheck,
    title: "Smart quality gate",
    text: "Blurry or poorly illuminated scans are rejected before diagnosis so uncertain predictions never pollute the queue.",
    span: "md:col-span-2",
  },
  {
    icon: Siren,
    title: "Smart triage",
    text: "Urgent and proliferative cases automatically jump the queue so clinicians review critical patients first.",
    span: "md:col-span-2",
  },
  {
    icon: CalendarClock,
    title: "Follow-up tracking",
    text: "Referrals and specialist appointments are tracked until the patient is seen — no one falls through the cracks.",
    span: "md:col-span-2",
  },
];

function Features() {
  return (
    <section className="mt-20">
      <div className="mx-auto max-w-xl text-center">
        <h2 className="font-display text-3xl font-medium tracking-tight text-slate-900">
          Built for real clinical workflows
        </h2>
        <p className="mt-2.5 text-sm text-slate-500">
          More than a classifier — an end-to-end safety net from image capture to specialist visit.
        </p>
      </div>

      <div className="mt-8 grid gap-4 md:grid-cols-6">
        {FEATURES.map(({ icon: Icon, title, text, span, badge, accent }) => (
          <div
            key={title}
            className={`group flex flex-col justify-between rounded-2xl p-6 shadow-xs ring-1 transition-all hover:-translate-y-0.5 hover:shadow-md ${span} ${
              accent
                ? "bg-gradient-to-br from-teal-50/70 via-white/80 to-white/60 ring-teal-200/80 backdrop-blur-sm"
                : "bg-white/75 ring-slate-200/80 backdrop-blur-sm"
            }`}
          >
            <div>
              <div className="flex items-center justify-between gap-2">
                <span
                  className={`grid size-10 place-items-center rounded-xl ring-1 ${
                    accent
                      ? "bg-teal-700 text-white ring-teal-700"
                      : "bg-teal-50 text-teal-700 ring-teal-200/70"
                  }`}
                >
                  <Icon className="size-5" />
                </span>

                {badge && (
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-600">
                    {badge}
                  </span>
                )}
              </div>

              <h3 className="mt-5 text-base font-semibold text-slate-900">{title}</h3>
              <p className="mt-2 text-[13.5px] leading-relaxed text-slate-500">{text}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ----------------------- multilingual retina passport ---------------------- */

type LangCode = "EN" | "RO" | "DE" | "FR" | "ES";

const PASSPORT_TRANSLATIONS: Record<
  LangCode,
  {
    languageName: string;
    diagnosis: string;
    urgency: string;
    recommendation: string;
    disclaimer: string;
  }
> = {
  EN: {
    languageName: "English",
    diagnosis: "Moderate Non-Proliferative Diabetic Retinopathy (Grade 2)",
    urgency: "Referable · Specialist Review",
    recommendation:
      "Schedule comprehensive dilated ophthalmological examination within 3 months.",
    disclaimer: "AI-assisted screening summary — verify clinically.",
  },
  RO: {
    languageName: "Română",
    diagnosis: "Retinopatie Diabetică Neproliferativă Moderată (Grad 2)",
    urgency: "Trimitere · Evaluare Specialist",
    recommendation:
      "Programați un examen oftalmologic complet cu dilatare pupilară în termen de 3 luni.",
    disclaimer: "Rezumat de screening asistat de AI — necesită validare clinică.",
  },
  DE: {
    languageName: "Deutsch",
    diagnosis: "Moderate nicht-proliferative diabetische Retinopathie (Grad 2)",
    urgency: "Überweisung · Facharztprüfung",
    recommendation:
      "Augenärztliche Untersuchung mit Pupillenerweiterung innerhalb von 3 Monaten vereinbaren.",
    disclaimer: "KI-gestützte Screening-Zusammenfassung — klinisch prüfen.",
  },
  FR: {
    languageName: "Français",
    diagnosis: "Rétinopathie diabétique non proliférante modérée (Grade 2)",
    urgency: "Orientation · Avis Spécialisé",
    recommendation:
      "Planifier un examen ophtalmologique complet avec dilatation sous 3 mois.",
    disclaimer: "Résumé de dépistage assisté par IA — à valider cliniquement.",
  },
  ES: {
    languageName: "Español",
    diagnosis: "Retinopatía diabética no proliferativa moderada (Grado 2)",
    urgency: "Derivable · Evaluación Especializada",
    recommendation:
      "Programar examen oftalmológico completo con dilatación dentro de los próximos 3 meses.",
    disclaimer: "Resumen de cribado asistido por IA — verificar clínicamente.",
  },
};

function RetinaPassportSpotlight() {
  const [lang, setLang] = useState<LangCode>("EN");
  const current = PASSPORT_TRANSLATIONS[lang];

  return (
    <section className="mt-20">
      <div className="grid items-center gap-8 rounded-3xl bg-white/75 p-6 shadow-xs ring-1 ring-slate-200/80 backdrop-blur-sm sm:p-10 lg:grid-cols-12">
        {/* Left Description */}
        <div className="lg:col-span-5">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-teal-50 px-3 py-1 text-xs font-medium text-teal-800 ring-1 ring-teal-200/80">
            <FileCheck2 className="size-3.5 text-teal-600" /> Cross-Border Continuity
          </span>
          <h2 className="mt-4 font-display text-3xl font-medium tracking-tight text-slate-900">
            European Retina Passport
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-slate-600">
            Whether a patient is screened in Timișoara and referred in Vienna or Madrid, their
            standardized ICDR grade, Grad-CAM visual evidence, and referral timeline travel with
            them in 5 languages.
          </p>

          <div className="mt-6 flex flex-wrap gap-1.5">
            {(Object.keys(PASSPORT_TRANSLATIONS) as LangCode[]).map((code) => (
              <button
                key={code}
                type="button"
                onClick={() => setLang(code)}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                  lang === code
                    ? "bg-teal-700 text-white shadow-xs"
                    : "bg-slate-100 text-slate-600 hover:bg-teal-50 hover:text-teal-800"
                }`}
              >
                {code} · {PASSPORT_TRANSLATIONS[code].languageName}
              </button>
            ))}
          </div>
        </div>

        {/* Right Interactive Passport Card */}
        <div className="lg:col-span-7">
          <div className="rounded-2xl border border-slate-200 bg-slate-100/70 p-5 sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-4">
              <div>
                <p className="text-[11px] font-semibold tracking-wider text-teal-700 uppercase">
                  EU Standardized Retinal Screening Record
                </p>
                <p className="mt-0.5 font-mono text-xs text-slate-500">
                  ID: EU-RET-2026-8492 · Language: {current.languageName}
                </p>
              </div>
              <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800 ring-1 ring-amber-200">
                {current.urgency}
              </span>
            </div>

            <div className="mt-4 space-y-3">
              <div>
                <p className="text-[11px] font-medium text-slate-400 uppercase">
                  AI Screening Finding
                </p>
                <p className="mt-0.5 text-sm font-semibold text-slate-900">{current.diagnosis}</p>
              </div>

              <div>
                <p className="text-[11px] font-medium text-slate-400 uppercase">
                  Recommended Clinical Action
                </p>
                <p className="mt-0.5 text-sm text-slate-700">{current.recommendation}</p>
              </div>
            </div>

            <div className="mt-5 flex items-center justify-between border-t border-slate-200/80 pt-3 text-[11px] text-slate-400">
              <span>{current.disclaimer}</span>
              <span className="font-mono font-medium text-slate-500">ICDR 0–4</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ------------------------- glass-box ai trust section ---------------------- */

const TRUST_PILLARS = [
  {
    icon: ShieldAlert,
    title: "Automated Quality Gate",
    text: "Deterministic blur, framing, and illumination checks reject unusable fundus images before inference runs — eliminating silent false negatives from poor captures.",
  },
  {
    icon: Sparkles,
    title: "Visual Grad-CAM Explanations",
    text: "Every severity estimate is paired with a spatial heatmap highlighting microaneurysms, hemorrhages, and exudates so clinicians can verify what drove the score.",
  },
  {
    icon: UserCheck,
    title: "Human-in-the-Loop Triage",
    text: "Built strictly as clinical decision support to prioritize specialist queues — never as an autonomous diagnostic replacement.",
  },
];

function GlassBoxTrust() {
  return (
    <section className="mt-20">
      <div className="rounded-3xl bg-slate-100/70 p-8 ring-1 ring-slate-200/90 backdrop-blur-sm sm:p-10">
        <div className="max-w-2xl">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-teal-50 px-3 py-1 text-xs font-medium text-teal-800 ring-1 ring-teal-200/80">
            <Lock className="size-3.5 text-teal-600" /> Glass-Box Clinical AI
          </span>
          <h2 className="mt-4 font-display text-3xl font-medium tracking-tight text-slate-900">
            Designed to earn clinical trust, not demand blind faith
          </h2>
          <p className="mt-2.5 text-sm leading-relaxed text-slate-600">
            Healthcare professionals cannot act on black-box numbers. Every layer of RetinaAI
            Nexus enforces transparency, image integrity, and specialist oversight.
          </p>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {TRUST_PILLARS.map(({ icon: Icon, title, text }) => (
            <div
              key={title}
              className="rounded-2xl bg-white/75 p-5 shadow-xs ring-1 ring-slate-200/80 backdrop-blur-sm"
            >
              <span className="grid size-9 place-items-center rounded-xl bg-teal-50 text-teal-700 ring-1 ring-teal-200/70">
                <Icon className="size-4.5" />
              </span>
              <h3 className="mt-4 text-sm font-semibold text-slate-900">{title}</h3>
              <p className="mt-1.5 text-[13px] leading-relaxed text-slate-600">{text}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------- how it works ------------------------------ */

const STEPS = [
  {
    icon: Upload,
    title: "Capture & upload",
    text: "A standard fundus photo, straight from the camera.",
  },
  {
    icon: Activity,
    title: "AI analysis",
    text: "Quality gate, severity grade, heatmap, triage decision.",
  },
  {
    icon: CalendarClock,
    title: "Act & follow up",
    text: "Passport report, referral, and tracking until the visit happens.",
  },
];

function HowItWorks() {
  return (
    <section className="mt-20">
      <h2 className="text-center font-display text-3xl font-medium tracking-tight text-slate-900">
        Three steps, one journey
      </h2>

      <div className="relative mt-8 grid gap-4 md:grid-cols-3">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute top-11 right-16 left-16 hidden border-t-2 border-dashed border-slate-200 md:block"
        />

        {STEPS.map(({ icon: Icon, title, text }, i) => (
          <div
            key={title}
            className="relative rounded-2xl bg-white/75 p-6 shadow-xs ring-1 ring-slate-200/80 backdrop-blur-sm"
          >
            <span className="absolute top-5 right-5 font-display text-2xl font-medium text-slate-200">
              {String(i + 1).padStart(2, "0")}
            </span>
            <span className="relative z-10 grid size-9 place-items-center rounded-xl bg-teal-700 text-white ring-4 ring-white">
              <Icon className="size-4.5" />
            </span>
            <h3 className="mt-4 text-sm font-semibold text-slate-900">{title}</h3>
            <p className="mt-1.5 text-[13px] leading-relaxed text-slate-500">{text}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

/* --------------------------------- footer ---------------------------------- */

function Footer() {
  return (
    <footer className="mt-24 border-t border-slate-200/80 py-8 text-center">
      <div className="inline-flex items-center gap-2 text-xs font-semibold text-slate-700">
        <Eye className="size-4 text-teal-700" />
        RetinaAI Nexus · Detect Early. Protect Vision. Save Sight.
      </div>
      <p className="mx-auto mt-2 max-w-xl text-[11px] leading-relaxed text-slate-400">
        Research &amp; educational demonstration prototype only — not intended for clinical
        diagnosis or autonomous medical decision-making.
      </p>
    </footer>
  );
}

/* ---------------------------------- page ----------------------------------- */

export default function LandingPage() {
  return (
    <div className="relative">
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-x-0 top-0 -z-10 h-[540px] bg-[radial-gradient(ellipse_80%_55%_at_50%_-10%,rgba(20,184,166,0.16),rgba(13,148,136,0.05)_55%,transparent_100%)]"
      />

      <Hero />
      <ClinicalImpact />
      <DemoStrip />
      <Features />
      <RetinaPassportSpotlight />
      <GlassBoxTrust />
      <HowItWorks />
      <Footer />
    </div>
  );
}