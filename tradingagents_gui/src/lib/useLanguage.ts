/**
 * Hook to get the current UI language from the config store.
 * Returns "zh" for Chinese, "en" for English.
 */
import { useConfigStore } from "../stores/useConfigStore";

export function useLanguage(): string {
  return useConfigStore((s) => s.config.language) === "English" ? "en" : "zh";
}
