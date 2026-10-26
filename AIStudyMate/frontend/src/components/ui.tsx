import { AlertCircle, LoaderCircle, Sparkles } from "lucide-react";

export const buttonClass = "inline-flex items-center justify-center gap-2 rounded-xl bg-ocean px-4 py-2.5 font-semibold text-white shadow-sm transition hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50";
export const inputClass = "w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100";
export const cardClass = "rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card";

export function FullPageLoader({ label = "Đang tải..." }: { label?: string }) {
  return <div className="grid min-h-screen place-items-center bg-cloud"><div className="flex items-center gap-3 text-slate-600"><LoaderCircle className="animate-spin text-ocean" />{label}</div></div>;
}
export function Loading({ label = "Đang tải dữ liệu..." }: { label?: string }) {
  return <div className="flex items-center justify-center gap-2 py-12 text-slate-500"><LoaderCircle className="h-5 w-5 animate-spin" />{label}</div>;
}
export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return <div role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-800"><div className="flex gap-3"><AlertCircle className="shrink-0" /><div><p className="font-semibold">Không thể tải dữ liệu</p><p className="mt-1 text-sm">{message}</p>{retry && <button onClick={retry} className="mt-3 font-semibold underline">Thử lại</button>}</div></div></div>;
}
export function EmptyState({ title, description, action }: { title: string; description: string; action?: React.ReactNode }) {
  return <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-14 text-center"><Sparkles className="mx-auto mb-3 text-blue-400" /><h3 className="font-bold text-ink">{title}</h3><p className="mx-auto mt-2 max-w-md text-sm text-slate-500">{description}</p>{action && <div className="mt-5">{action}</div>}</div>;
}
export function PageHeader({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description: string; action?: React.ReactNode }) {
  return <header className="mb-7 flex flex-col justify-between gap-4 md:flex-row md:items-end"><div>{eyebrow && <p className="mb-2 text-xs font-bold uppercase tracking-[.2em] text-ocean">{eyebrow}</p>}<h1 className="text-3xl font-extrabold tracking-tight text-ink">{title}</h1><p className="mt-2 max-w-2xl text-slate-500">{description}</p></div>{action}</header>;
}
export function Badge({ children, tone = "blue" }: { children: React.ReactNode; tone?: "blue" | "green" | "amber" | "red" | "slate" }) {
  const colors = { blue: "bg-blue-50 text-blue-700", green: "bg-emerald-50 text-emerald-700", amber: "bg-amber-50 text-amber-700", red: "bg-red-50 text-red-700", slate: "bg-slate-100 text-slate-600" };
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-bold ${colors[tone]}`}>{children}</span>;
}
