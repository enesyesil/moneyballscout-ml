import type { ReactNode } from "react";
import { Link } from "react-router";
import type { PlayerRow } from "../api/client";
import { POSITION_LABEL, ratingTone } from "../lib/format";

export function Card({ title, subtitle, action, children, className = "" }: {
  title?: ReactNode; subtitle?: ReactNode; action?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <section className={`card p-4 sm:p-5 min-w-0 ${className}`}>
      {(title || action) && (
        <header className="mb-3 flex items-start justify-between gap-3">
          <div className="min-w-0">
            {title && <h2 className="text-[15px] font-semibold tracking-tight">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-[13px] text-ink-3">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="text-[12px] uppercase tracking-wide text-ink-3">{label}</div>
      <div className="num mt-0.5 text-xl font-semibold tracking-tight">{value}</div>
      {hint && <div className="mt-0.5 text-[12px] text-ink-3">{hint}</div>}
    </div>
  );
}

export function RatingBadge({ value, size = "md" }: { value: number | null | undefined; size?: "sm" | "md" | "lg" }) {
  const cls = size === "lg" ? "h-10 min-w-12 text-lg" : size === "sm" ? "h-6 min-w-9 text-[12px]" : "h-7 min-w-10 text-[13px]";
  return (
    <span className={`num inline-flex items-center justify-center rounded-md px-1.5 font-semibold ${cls} ${ratingTone(value)}`}>
      {value === null || value === undefined ? "–" : value.toFixed(1)}
    </span>
  );
}

export function PosChip({ pos }: { pos: string }) {
  return (
    <span title={POSITION_LABEL[pos]} className="rounded border border-line px-1.5 py-px text-[11px] font-medium text-ink-2">
      {pos}
    </span>
  );
}

export function Avatar({ src, name, size = 32 }: { src?: string | null; name: string; size?: number }) {
  const initials = name.split(/\s+/).map((s) => s[0]).slice(0, 2).join("");
  return src ? (
    <img src={src} alt="" width={size} height={size} className="shrink-0 rounded-full bg-surface-2 object-cover" style={{ width: size, height: size }} loading="lazy" />
  ) : (
    <span className="inline-flex shrink-0 items-center justify-center rounded-full bg-surface-2 text-[11px] font-semibold text-ink-2" style={{ width: size, height: size }}>
      {initials}
    </span>
  );
}

export function TeamLogo({ src, size = 20 }: { src?: string | null; size?: number }) {
  return src ? <img src={src} alt="" width={size} height={size} className="shrink-0 object-contain" loading="lazy" /> : (
    <span className="inline-block shrink-0 rounded-full bg-surface-2" style={{ width: size, height: size }} />
  );
}

export function PlayerCell({ p }: { p: Pick<PlayerRow, "id" | "name" | "photo" | "team" | "position_group"> }) {
  return (
    <Link to={`/players/${p.id}`} className="group flex min-w-0 items-center gap-2.5">
      <Avatar src={p.photo} name={p.name} />
      <span className="min-w-0">
        <span className="block truncate font-medium group-hover:text-accent">{p.name}</span>
        <span className="flex items-center gap-1.5 truncate text-[12px] text-ink-3">
          <PosChip pos={p.position_group} />
          {p.team?.name}
        </span>
      </span>
    </Link>
  );
}

export function Segmented<T extends string>({ value, onChange, options, label }: {
  value: T; onChange: (v: T) => void; options: { value: T; label: string }[]; label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-lg border border-line bg-surface p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={`rounded-md px-2.5 py-1 text-[13px] font-medium transition-colors ${
            value === o.value ? "bg-ink text-surface" : "text-ink-2 hover:text-ink"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Select({ value, onChange, options, label }: {
  value: string; onChange: (v: string) => void; options: { value: string; label: string }[]; label: string;
}) {
  return (
    <label className="inline-flex items-center gap-2 text-[13px] text-ink-2">
      <span>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}
        className="rounded-lg border border-line bg-surface px-2 py-1.5 text-[13px] text-ink">
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  );
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return <div className="animate-pulse py-10 text-center text-sm text-ink-3">{label}…</div>;
}

export function ErrorBox({ error }: { error: unknown }) {
  return (
    <div className="rounded-lg border border-line bg-surface-2 p-4 text-sm text-ink-2">
      <strong className="text-ink">Couldn't load this.</strong> {error instanceof Error ? error.message : String(error)}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="py-8 text-center text-sm text-ink-3">{children}</div>;
}

export function Table({ children }: { children: ReactNode }) {
  return (
    <div className="-mx-4 overflow-x-auto sm:-mx-5">
      <table className="w-full min-w-[560px] border-collapse text-[13px]">{children}</table>
    </div>
  );
}

export const th = "px-4 sm:first:pl-5 sm:last:pr-5 py-2 text-left text-[11px] font-medium uppercase tracking-wide text-ink-3 border-b border-line whitespace-nowrap";
export const td = "px-4 sm:first:pl-5 sm:last:pr-5 py-2 border-b border-line align-middle";
