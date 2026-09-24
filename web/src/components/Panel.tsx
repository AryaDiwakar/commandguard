import type { ReactNode } from "react";

export function Panel({
  title,
  right,
  children,
  className = "",
}: {
  title?: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={"glass-panel p-4 " + className}>
      {(title || right) && (
        <header className="mb-2 flex items-center justify-between gap-2">
          {title && <h3 className="hud-label text-slate-300">{title}</h3>}
          {right}
        </header>
      )}
      {children}
    </section>
  );
}
