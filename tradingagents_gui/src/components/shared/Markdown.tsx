/**
 * Markdown — the single active markdown renderer for the platform (ticket 03).
 *
 * Standard `react-markdown` + `remark-gfm`, styled with the compact
 * `.prose-compact` theme (index.css). Replaces the self-built
 * `astock/MarkdownRenderer` at every call site; the legacy file is kept with an
 * `@deprecated` note until the user decides whether to remove it.
 *
 * Why unify: the legacy renderer only understood headings, pipe tables and
 * plain text — no lists, no inline emphasis, no semantic `<hN>` anchors (see
 * `markdown-equivalence.test.tsx`). react-markdown handles all of them and is
 * already what the report page uses.
 *
 * Prop signature is intentionally identical to the legacy component
 * (`{ markdown, className }`) so migration is a path change only.
 */

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  markdown: string;
  className?: string;
}

export default function MarkdownRenderer({ markdown, className = "" }: Props) {
  if (!markdown) return null;

  return (
    <div className={`prose-compact ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Wide data tables must scroll, not blow out a 320px panel.
          table: ({ children }) => (
            <div className="my-3 overflow-x-auto">
              <table>{children}</table>
            </div>
          ),
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
