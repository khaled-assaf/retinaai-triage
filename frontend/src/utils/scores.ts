/**
 * Integer percentages that add up to exactly 100 (largest-remainder method).
 * Display only: the model outputs themselves are never changed. Same method as the
 * backend passport (backend/app/reports/content.py round_to_100).
 */
export function roundTo100(probs: number[]): number[] {
  const total = probs.reduce((a, b) => a + b, 0) || 1;
  const raw = probs.map((p) => (p / total) * 100);
  const floors = raw.map(Math.floor);
  let missing = 100 - floors.reduce((a, b) => a + b, 0);
  const order = raw
    .map((x, i) => ({ i, frac: x - floors[i], x }))
    .sort((a, b) => b.frac - a.frac || b.x - a.x);
  for (const { i } of order) {
    if (missing <= 0) break;
    floors[i] += 1;
    missing -= 1;
  }
  return floors;
}
