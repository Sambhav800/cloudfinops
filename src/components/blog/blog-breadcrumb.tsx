import Link from "next/link";

interface BreadcrumbItem {
  label: string;
  href?: string;
}

export function BlogBreadcrumb({ items }: { items: BreadcrumbItem[] }) {
  return (
    <nav aria-label="Breadcrumb" className="mb-6">
      <ol className="flex items-center gap-1.5 text-[13px] text-zinc-500">
        {items.map((item, i) => (
          <li key={item.label} className="flex items-center gap-1.5">
            {i > 0 && <span className="text-zinc-700">/</span>}
            {item.href ? (
              <Link
                href={item.href}
                className="hover:text-zinc-300 transition-colors"
              >
                {item.label}
              </Link>
            ) : (
              <span className="text-zinc-400 truncate max-w-[200px]">
                {item.label}
              </span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
