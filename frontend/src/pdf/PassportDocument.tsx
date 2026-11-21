import { Document, Font, Image, Page, StyleSheet, Text, View } from "@react-pdf/renderer";
import type { Case } from "../types";
import { PASSPORT_STRINGS, type PassportLang } from "../i18n/passport";

/* Unicode font — covers Romanian ș/ț, French œ, German ß, Spanish ñ.
   Browser: served from public/ at the root. Node (smoke test): resolve from cwd. */
const FONT_BASE =
  typeof window === "undefined"
    ? `${String((globalThis as { process?: { cwd?: () => string } }).process?.cwd?.() ?? ".")}/public`
    : "";
Font.register({
  family: "NotoSans",
  fonts: [
    { src: `${FONT_BASE}/fonts/NotoSans-Regular.ttf` },
    { src: `${FONT_BASE}/fonts/NotoSans-Bold.ttf`, fontWeight: 700 },
  ],
});

const TEAL = "#0f766e";
const SLATE_900 = "#0f172a";
const SLATE_500 = "#64748b";
const SLATE_300 = "#cbd5e1";

const styles = StyleSheet.create({
  page: {
    fontFamily: "NotoSans",
    fontSize: 10,
    color: SLATE_900,
    padding: 44,
  },
  headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" },
  title: { fontSize: 20, fontWeight: 700, color: TEAL },
  subtitle: { fontSize: 10, color: SLATE_500, marginTop: 3 },
  brand: { fontSize: 9, color: SLATE_500, textAlign: "right" },
  divider: { height: 2.5, backgroundColor: TEAL, marginVertical: 16, borderRadius: 2 },
  sectionLabel: {
    fontSize: 8,
    fontWeight: 700,
    letterSpacing: 1.2,
    color: SLATE_500,
    textTransform: "uppercase",
    marginBottom: 6,
  },
  metaGrid: { flexDirection: "row", gap: 24, marginBottom: 18 },
  metaItem: { flex: 1 },
  metaKey: { fontSize: 8, color: SLATE_500 },
  metaVal: { fontSize: 10.5, fontWeight: 700, marginTop: 2 },
  card: {
    backgroundColor: "#f8fafc",
    borderRadius: 8,
    padding: 14,
    marginBottom: 12,
    border: `1 solid ${SLATE_300}`,
  },
  gradeRow: { flexDirection: "row", alignItems: "center", gap: 14 },
  gradeNum: { fontSize: 34, fontWeight: 700, color: TEAL },
  gradeText: { flex: 1 },
  gradeLabel: { fontSize: 8, color: SLATE_500 },
  gradeValue: { fontSize: 12, fontWeight: 700, marginTop: 2 },
  confidence: { fontSize: 9, color: SLATE_500, marginTop: 8 },
  note: {
    fontSize: 8.5,
    color: "#92400e",
    backgroundColor: "#fef3c7",
    borderRadius: 6,
    padding: 8,
    marginTop: 10,
  },
  actionValue: { fontSize: 11, fontWeight: 700, color: TEAL },
  actionText: { fontSize: 10, marginTop: 3, lineHeight: 1.4 },
  footer: {
    position: "absolute",
    bottom: 36,
    left: 44,
    right: 44,
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    borderTop: `1 solid ${SLATE_300}`,
    paddingTop: 12,
  },
  qrBlock: { flexDirection: "row", alignItems: "flex-end", gap: 10 },
  scan: { fontSize: 7.5, color: SLATE_500, maxWidth: 110 },
  disclaimerBlock: { flex: 1, marginLeft: 20 },
  disclaimer: { fontSize: 7.5, color: SLATE_500, lineHeight: 1.4, textAlign: "right" },
  footerNote: { fontSize: 7.5, color: SLATE_500, marginTop: 4, textAlign: "right" },
});

interface Props {
  caseData: Case;
  lang: PassportLang;
  qrDataUrl: string;
  /** dataURL of the fundus image; omit to skip */
  fundusDataUrl?: string | null;
}

export function PassportDocument({ caseData, lang, qrDataUrl, fundusDataUrl }: Props) {
  const t = PASSPORT_STRINGS[lang];
  const { prediction, quality, triage } = caseData;
  const uncertain = triage.level === "review";
  const date = new Date(caseData.created_at).toLocaleDateString(lang, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  return (
    <Document title={`${t.title} — ${caseData.case_id}`} language={lang}>
      <Page size="A4" style={styles.page}>
        {/* Header */}
        <View style={styles.headerRow}>
          <View>
            <Text style={styles.title}>{t.title}</Text>
            <Text style={styles.subtitle}>{t.subtitle}</Text>
          </View>
          <Text style={styles.brand}>
            RetinaAI Nexus{"\n"}
            {t.languageName}
          </Text>
        </View>
        <View style={styles.divider} />

        {/* Meta */}
        <View style={styles.metaGrid}>
          <View style={styles.metaItem}>
            <Text style={styles.metaKey}>{t.reportId}</Text>
            <Text style={styles.metaVal}>{caseData.case_id}</Text>
          </View>
          <View style={styles.metaItem}>
            <Text style={styles.metaKey}>{t.patientRef}</Text>
            <Text style={styles.metaVal}>{caseData.patient_ref ?? "—"}</Text>
          </View>
          <View style={styles.metaItem}>
            <Text style={styles.metaKey}>{t.examDate}</Text>
            <Text style={styles.metaVal}>{date}</Text>
          </View>
          <View style={styles.metaItem}>
            <Text style={styles.metaKey}>Model</Text>
            <Text style={styles.metaVal}>
              {caseData.model_version} · {caseData.processing_ms} ms
            </Text>
          </View>
        </View>

        {/* Findings */}
        <Text style={styles.sectionLabel}>{t.findingsSection}</Text>
        <View style={styles.card}>
          {fundusDataUrl && (
            <Image
              src={fundusDataUrl}
              style={{ width: 88, height: 66, borderRadius: 6, marginBottom: 10 }}
            />
          )}
          {prediction ? (
            <View style={styles.gradeRow}>
              <Text style={styles.gradeNum}>{prediction.grade}</Text>
              <View style={styles.gradeText}>
                <Text style={styles.gradeLabel}>{t.gradeLabel}</Text>
                <Text style={styles.gradeValue}>{t.severityLabels[prediction.grade]}</Text>
                <Text style={styles.confidence}>
                  {t.confidence}: {(prediction.confidence * 100).toFixed(0)}%
                </Text>
              </View>
            </View>
          ) : (
            <Text style={styles.gradeValue}>{t.qualityFailed}</Text>
          )}
          {uncertain && <Text style={styles.note}>{t.uncertaintyNote}</Text>}
        </View>

        {/* Quality */}
        <Text style={styles.sectionLabel}>{t.qualitySection}</Text>
        <View style={styles.card}>
          <Text style={styles.actionText}>
            {quality.passed ? `✓ ${t.qualityPassed}` : `✗ ${t.qualityFailed}`}
            {quality.reason !== "OK" ? ` — ${quality.reason}` : ""}
          </Text>
        </View>

        {/* Recommended action */}
        <Text style={styles.sectionLabel}>{t.triageSection}</Text>
        <View style={styles.card}>
          <Text style={styles.actionValue}>{triage.label}</Text>
          <Text style={styles.actionText}>{triage.action}</Text>
        </View>

        {/* Footer */}
        <View style={styles.footer}>
          <View style={styles.qrBlock}>
            <Image src={qrDataUrl} style={{ width: 64, height: 64 }} />
            <Text style={styles.scan}>{t.scanForCase}</Text>
          </View>
          <View style={styles.disclaimerBlock}>
            <Text style={styles.disclaimer}>{t.disclaimer}</Text>
            <Text style={styles.footerNote}>{t.footerNote}</Text>
          </View>
        </View>
      </Page>
    </Document>
  );
}
