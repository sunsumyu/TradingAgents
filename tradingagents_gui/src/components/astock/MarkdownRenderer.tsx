/**
 * @deprecated Legacy self-built markdown renderer — REPLACED by `Markdown`
 * in `components/shared/Markdown.tsx` (ticket 03). It only understood
 * headings, pipe tables and plain text: no lists, no inline emphasis, and no
 * semantic `<hN>` tags (see `shared/markdown-equivalence.test.tsx`).
 *
 * Kept as a thin delegation so any straggler import keeps working with the
 * unified renderer — there is exactly ONE active implementation. Do not add
 * features here. Migrate imports to `components/shared/Markdown`; remove this
 * file only with the user's explicit go-ahead.
 */

import Markdown from "../shared/Markdown";

interface Props {
  markdown: string;
  className?: string;
}

export default function MarkdownRenderer({ markdown, className = "" }: Props) {
  return <Markdown markdown={markdown} className={className} />;
}
