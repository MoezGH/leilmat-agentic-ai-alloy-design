"use client";

/**
 * MarkdownMessage — renders LLM markdown output with a compact dark
 * theme tuned for the Global AI panel (and reusable by Local AI / the
 * interpret blocks).
 *
 * The LLM emits standard markdown: ``**bold**``, ``### headers``,
 * ``- bullets``, ``1. numbered``, ``` `inline code` ```, ``> quotes``,
 * tables, links.  Until now the chat bubble dumped it raw via
 * ``whitespace-pre-wrap`` so users saw literal asterisks and hashes.
 *
 * We use ``react-markdown`` + ``remark-gfm`` (GitHub-flavoured: tables,
 * strikethrough, task lists, autolinks) — the standard, battle-tested
 * renderer for streaming LLM output.  Incomplete markdown mid-stream
 * renders gracefully (react-markdown just renders what parses so far).
 *
 * Every element gets an explicit className so the typography matches
 * the panel: tight line-height, slate body text, sky accent on links
 * + inline code, smaller-than-default headers (the panel is only
 * 420 px wide so h1 = 14 px not 32 px).
 *
 * Security: react-markdown does NOT render raw HTML by default (no
 * ``rehype-raw``), so LLM-injected ``<script>`` / ``<img onerror>`` are
 * inert — they render as literal text.  Links get ``rel="noopener
 * noreferrer"`` + ``target="_blank"``.
 */
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";


// Component overrides — keyed by HTML tag react-markdown produces.
const COMPONENTS: Components = {
  // ── Headings — scaled down for the 420 px panel ────────────────
  h1: ({ children }) => (
    <h3 className="mt-3 mb-1.5 text-[14px] font-semibold text-fg tracking-tight first:mt-0">
      {children}
    </h3>
  ),
  h2: ({ children }) => (
    <h4 className="mt-3 mb-1.5 text-[13px] font-semibold text-fg tracking-tight first:mt-0">
      {children}
    </h4>
  ),
  h3: ({ children }) => (
    <h5 className="mt-2.5 mb-1 text-[12.5px] font-semibold text-fg tracking-tight first:mt-0">
      {children}
    </h5>
  ),
  // h4-h6 collapse to the same small-caps eyebrow.
  h4: ({ children }) => (
    <p className="mt-2 mb-1 text-[10.5px] font-semibold uppercase tracking-[0.1em] text-muted first:mt-0">
      {children}
    </p>
  ),

  // ── Paragraphs + inline emphasis ───────────────────────────────
  p: ({ children }) => (
    <p className="my-1.5 text-[13px] leading-relaxed text-fg first:mt-0 last:mb-0">
      {children}
    </p>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-fg">{children}</strong>
  ),
  em: ({ children }) => <em className="italic text-muted">{children}</em>,
  del: ({ children }) => (
    <del className="text-subtle line-through">{children}</del>
  ),

  // ── Lists — tight, sky-tinted markers ──────────────────────────
  ul: ({ children }) => (
    <ul className="my-1.5 ml-1 space-y-1 first:mt-0 last:mb-0">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="my-1.5 ml-1 list-decimal space-y-1 pl-3.5 marker:text-subtle first:mt-0 last:mb-0">
      {children}
    </ol>
  ),
  li: ({ children, ...props }) => {
    // ``react-markdown`` flags GFM task-list items; render those with a
    // checkbox glyph instead of a bullet.
    const ordered = (props as { node?: { parentNode?: { tagName?: string } } })
      .node?.parentNode?.tagName === "ol";
    if (ordered) {
      return <li className="text-[13px] leading-relaxed text-fg">{children}</li>;
    }
    return (
      <li className="relative pl-3.5 text-[13px] leading-relaxed text-fg">
        <span className="absolute left-0 top-[0.55em] h-1 w-1 -translate-y-1/2 rounded-full bg-fg/10" />
        {children}
      </li>
    );
  },

  // ── Inline + block code ────────────────────────────────────────
  code: ({ className, children }) => {
    const isBlock = (className ?? "").includes("language-");
    if (isBlock) {
      return (
        <code className="block">{children}</code>
      );
    }
    return (
      <code className="rounded bg-fg/10 px-1 py-0.5 font-mono text-[11.5px] text-fg">
        {children}
      </code>
    );
  },
  pre: ({ children }) => (
    <pre className="my-2 overflow-x-auto rounded-md border border-line bg-black/30 p-2.5 font-mono text-[11px] leading-relaxed text-muted">
      {children}
    </pre>
  ),

  // ── Blockquotes (the LLM uses these for caveats / "note:" asides) ─
  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-2 border-line pl-3 text-[12.5px] italic text-muted">
      {children}
    </blockquote>
  ),

  // ── Links — open in a new tab, hardened ────────────────────────
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-fg underline decoration-dotted underline-offset-2 hover:text-fg transition-colors"
    >
      {children}
    </a>
  ),

  // ── Tables (GFM) — scrollable, hairline-bordered ───────────────
  table: ({ children }) => (
    <div className="my-2 overflow-x-auto">
      <table className="w-full border-collapse text-[11.5px]">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead>{children}</thead>,
  th: ({ children }) => (
    <th className="border-b border-line px-2 py-1 text-left font-semibold text-muted">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border-b border-line px-2 py-1 text-muted">
      {children}
    </td>
  ),

  // ── Horizontal rule ────────────────────────────────────────────
  hr: () => <hr className="my-3 border-line" />,
};


export function MarkdownMessage({ children }: { children: string }) {
  return (
    <div className="leil-markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={COMPONENTS}>
        {children}
      </ReactMarkdown>
    </div>
  );
}
