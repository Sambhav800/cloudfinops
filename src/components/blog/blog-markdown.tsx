import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

const components: Components = {
  h2: ({ children }) => {
    const text = String(children);
    const id = slugify(text);
    return (
      <h2
        id={id}
        className="text-[28px] font-semibold text-white mt-14 mb-4 scroll-mt-24"
      >
        {children}
      </h2>
    );
  },
  h3: ({ children }) => {
    const text = String(children);
    const id = slugify(text);
    return (
      <h3
        id={id}
        className="text-[20px] font-medium text-white mt-8 mb-3 scroll-mt-24"
      >
        {children}
      </h3>
    );
  },
  h4: ({ children }) => (
    <h4 className="text-[16px] font-semibold text-white mt-6 mb-2">
      {children}
    </h4>
  ),
  p: ({ children }) => (
    <p className="text-zinc-300 text-[16px] leading-[1.8] mb-5">{children}</p>
  ),
  ul: ({ children }) => (
    <ul className="list-disc list-outside pl-6 mb-5 space-y-2 text-zinc-300 text-[16px] leading-[1.8]">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal list-outside pl-6 mb-5 space-y-2 text-zinc-300 text-[16px] leading-[1.8]">
      {children}
    </ol>
  ),
  li: ({ children }) => <li className="pl-1">{children}</li>,
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-indigo-500 bg-indigo-500/[0.04] px-6 py-4 rounded-r-lg my-6 [&>p]:mb-0">
      {children}
    </blockquote>
  ),
  a: ({ href, children }) => {
    const isExternal = href?.startsWith("http");
    return (
      <a
        href={href}
        className="text-indigo-400 hover:text-indigo-300 underline underline-offset-2 transition-colors"
        {...(isExternal ? { target: "_blank", rel: "noopener noreferrer" } : {})}
      >
        {children}
      </a>
    );
  },
  table: ({ children }) => (
    <div className="overflow-x-auto my-6 rounded-xl border border-white/[0.08]">
      <table className="w-full text-sm text-left">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-white/[0.04] text-zinc-300 text-xs uppercase tracking-wider">
      {children}
    </thead>
  ),
  tbody: ({ children }) => (
    <tbody className="divide-y divide-white/[0.06]">{children}</tbody>
  ),
  tr: ({ children }) => (
    <tr className="hover:bg-white/[0.02] transition-colors">{children}</tr>
  ),
  th: ({ children }) => (
    <th className="px-4 py-3 font-medium text-zinc-200">{children}</th>
  ),
  td: ({ children }) => (
    <td className="px-4 py-3 text-zinc-400">{children}</td>
  ),
  code: ({ className, children }) => {
    const isBlock = className?.includes("language-");
    if (isBlock) {
      return (
        <div className="my-6 rounded-xl overflow-hidden border border-white/[0.08]">
          <div className="bg-[#0c0d12] px-5 py-4 overflow-x-auto">
            <code className="text-[13px] leading-relaxed text-zinc-300 font-mono">
              {children}
            </code>
          </div>
        </div>
      );
    }
    return (
      <code className="text-[14px] bg-white/[0.06] text-indigo-300 px-1.5 py-0.5 rounded font-mono">
        {children}
      </code>
    );
  },
  pre: ({ children }) => <>{children}</>,
  hr: () => (
    <hr className="my-10 border-0 h-px bg-gradient-to-r from-transparent via-white/[0.1] to-transparent" />
  ),
  strong: ({ children }) => (
    <strong className="text-white font-semibold">{children}</strong>
  ),
  img: ({ src, alt }) => (
    <figure className="my-8">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={alt || ""}
        className="rounded-xl border border-white/[0.08] w-full"
        loading="lazy"
      />
      {alt && (
        <figcaption className="text-center text-xs text-zinc-500 mt-3">
          {alt}
        </figcaption>
      )}
    </figure>
  ),
};

export function BlogMarkdown({ content }: { content: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {content}
    </ReactMarkdown>
  );
}
