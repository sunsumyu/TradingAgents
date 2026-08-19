/**
 * Build-time embedded ECharts minified source for offline HTML export.
 *
 * Uses Vite's `?raw` import to inline the file content as a string at build
 * time.  The dynamic import ensures this 1.1 MB chunk is code-split and only
 * loaded when the user clicks "Save HTML".
 */
export async function getEchartsMinJs(): Promise<string> {
  const mod = await import("echarts/dist/echarts.min.js?raw");
  return mod.default;
}
