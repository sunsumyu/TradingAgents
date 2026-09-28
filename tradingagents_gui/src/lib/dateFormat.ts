/**
 * Date formatting utilities for display.
 *
 * Converts YYYY-MM-DD → "2026年9月9日" for Chinese locales,
 * and "Sep 9, 2026" for English locales.
 */

/** Convert "2026-09-09" → "2026年9月9日" (Chinese) or "Sep 9, 2026" (English) */
export function formatDateDisplay(dateStr: string, locale: string = "zh"): string {
  if (!dateStr) return "";
  const m = dateStr.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
  if (!m) return dateStr; // fallback: show raw string
  const [, y, mm, dd] = m;
  const month = parseInt(mm, 10);
  const day = parseInt(dd, 10);
  if (locale.startsWith("zh")) {
    return `${y}年${month}月${day}日`;
  }
  // English fallback
  const d = new Date(Number(y), month - 1, day);
  return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

/** Short form: "09-09" or "9月9日" */
export function formatDateShort(dateStr: string, locale: string = "zh"): string {
  if (!dateStr) return "";
  const m = dateStr.match(/^\d{4}-(\d{1,2})-(\d{1,2})/);
  if (!m) return dateStr;
  const month = parseInt(m[1], 10);
  const day = parseInt(m[2], 10);
  if (locale.startsWith("zh")) {
    return `${month}月${day}日`;
  }
  return `${m[1]}-${m[2]}`;
}
