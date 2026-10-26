import { FormEvent, useState } from "react";
import { BrainCircuit, CheckCircle2 } from "lucide-react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { apiError } from "../lib/api";
import { buttonClass, inputClass } from "../components/ui";

function AuthFrame({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return <main className="grid min-h-screen bg-cloud lg:grid-cols-[1.05fr_.95fr]"><section className="hidden overflow-hidden bg-ink p-12 text-white lg:flex lg:flex-col lg:justify-between"><div className="flex items-center gap-3 text-xl font-black"><span className="grid h-11 w-11 place-items-center rounded-2xl bg-ocean">AI</span>StudyMate</div><div><p className="text-sm font-bold uppercase tracking-[.25em] text-blue-300">Learning workspace</p><h1 className="mt-5 max-w-xl text-5xl font-black leading-tight">Biến tài liệu của bạn thành trải nghiệm học chủ động.</h1><div className="mt-10 space-y-4 text-blue-100">{["Hỏi đáp có trích dẫn", "Study Agent đa bước", "Quiz AI và phân tích tiến độ"].map((item) => <p key={item} className="flex items-center gap-3"><CheckCircle2 className="text-mint" />{item}</p>)}</div></div><p className="text-sm text-blue-300">Dữ liệu học tập thuộc về bạn.</p></section><section className="grid place-items-center p-5"><div className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-7 shadow-card sm:p-9"><BrainCircuit className="mb-6 h-10 w-10 text-ocean" /><h2 className="text-3xl font-extrabold text-ink">{title}</h2><p className="mt-2 text-slate-500">{subtitle}</p>{children}</div></section></main>;
}

export function LoginPage() {
  const { user, login } = useAuth(); const nav = useNavigate(); const location = useLocation();
  const [form, setForm] = useState({ username: "", password: "" }); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/" replace />;
  const submit = async (event: FormEvent) => { event.preventDefault(); setError(""); if (!form.username || !form.password) return setError("Vui lòng nhập đầy đủ thông tin."); setBusy(true); try { await login(form.username, form.password); nav((location.state as { from?: string })?.from ?? "/", { replace: true }); } catch (e) { setError(apiError(e)); } finally { setBusy(false); } };
  return <AuthFrame title="Chào mừng trở lại" subtitle="Đăng nhập để tiếp tục hành trình học tập."><form onSubmit={submit} className="mt-8 space-y-4"><label className="block text-sm font-semibold">Tên đăng nhập hoặc email<input aria-label="Tên đăng nhập hoặc email" className={`${inputClass} mt-1.5`} value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} /></label><label className="block text-sm font-semibold">Mật khẩu<input aria-label="Mật khẩu" type="password" className={`${inputClass} mt-1.5`} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></label>{error && <p role="alert" className="text-sm text-red-600">{error}</p>}<button disabled={busy} className={`${buttonClass} w-full`}>{busy ? "Đang đăng nhập..." : "Đăng nhập"}</button></form><p className="mt-6 text-center text-sm text-slate-500">Chưa có tài khoản? <Link className="font-bold text-ocean" to="/register">Đăng ký</Link></p></AuthFrame>;
}

export function RegisterPage() {
  const { user, register } = useAuth(); const nav = useNavigate();
  const [form, setForm] = useState({ username: "", email: "", password: "", full_name: "" }); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/" replace />;
  const submit = async (event: FormEvent) => { event.preventDefault(); setError(""); if (form.username.length < 3 || !form.email.includes("@") || form.password.length < 8 || !form.full_name) return setError("Kiểm tra họ tên, email, username ≥ 3 và mật khẩu ≥ 8 ký tự."); setBusy(true); try { await register(form); nav("/"); } catch (e) { setError(apiError(e)); } finally { setBusy(false); } };
  return <AuthFrame title="Tạo tài khoản" subtitle="Bắt đầu xây dựng thư viện học tập của riêng bạn."><form onSubmit={submit} className="mt-7 space-y-3">{[["full_name", "Họ và tên"], ["username", "Tên đăng nhập"], ["email", "Email"], ["password", "Mật khẩu"]].map(([key, label]) => <label key={key} className="block text-sm font-semibold">{label}<input aria-label={label} type={key === "password" ? "password" : key === "email" ? "email" : "text"} className={`${inputClass} mt-1`} value={form[key as keyof typeof form]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} /></label>)}{error && <p role="alert" className="text-sm text-red-600">{error}</p>}<button disabled={busy} className={`${buttonClass} w-full`}>{busy ? "Đang tạo..." : "Tạo tài khoản"}</button></form><p className="mt-5 text-center text-sm text-slate-500">Đã có tài khoản? <Link className="font-bold text-ocean" to="/login">Đăng nhập</Link></p></AuthFrame>;
}
