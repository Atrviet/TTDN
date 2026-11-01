import { useState } from "react";
import { BarChart3, Bot, BrainCircuit, CalendarDays, FileText, GraduationCap, Layers3, LayoutDashboard, LogOut, Menu, MessageSquare, Network, Target, User, X } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";

const nav = [
  ["/", "Tổng quan", LayoutDashboard], ["/documents", "Tài liệu", FileText],
  ["/chat", "AI Chat", MessageSquare], ["/agent", "Study Agent", Bot],
  ["/quizzes", "Bài kiểm tra", BrainCircuit], ["/analytics", "Phân tích", BarChart3],
  ["/flashcards", "Flashcards", Layers3],
  ["/study-plans", "Kế hoạch học", CalendarDays],
  ["/tutor", "AI Tutor", GraduationCap],
  ["/knowledge-graphs", "Sơ đồ kiến thức", Network],
  ["/learning", "Điểm yếu học tập", Target],
  ["/profile", "Hồ sơ", User],
] as const;

export function AppShell() {
  const [open, setOpen] = useState(false); const { user, logout } = useAuth();
  const sidebar = <aside className="flex h-full w-72 flex-col bg-ink px-4 py-5 text-white"><div className="mb-8 flex items-center justify-between px-2"><div className="flex items-center gap-3"><div className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-blue-400 to-mint font-black">AI</div><div><p className="font-extrabold">StudyMate</p><p className="text-xs text-blue-200">Học thông minh hơn</p></div></div><button className="lg:hidden" onClick={() => setOpen(false)} aria-label="Đóng menu"><X /></button></div><nav className="space-y-1">{nav.map(([to, label, Icon]) => <NavLink key={to} to={to} end={to === "/"} onClick={() => setOpen(false)} className={({ isActive }) => `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition ${isActive ? "bg-white text-ink" : "text-blue-100 hover:bg-white/10"}`}><Icon className="h-5 w-5" />{label}</NavLink>)}</nav><div className="mt-auto border-t border-white/10 pt-4"><p className="truncate px-3 text-sm font-semibold">{user?.full_name}</p><p className="truncate px-3 text-xs text-blue-200">{user?.email}</p><button onClick={logout} className="mt-3 flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm text-blue-100 hover:bg-white/10"><LogOut className="h-4 w-4" />Đăng xuất</button></div></aside>;
  return <div className="min-h-screen bg-cloud"><div className={`fixed inset-0 z-40 bg-slate-950/40 lg:hidden ${open ? "block" : "hidden"}`} onClick={() => setOpen(false)} /><div className={`fixed inset-y-0 left-0 z-50 transition-transform lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>{sidebar}</div><div className="lg:pl-72"><header className="sticky top-0 z-30 flex h-16 items-center border-b border-slate-200 bg-white/90 px-4 backdrop-blur lg:hidden"><button onClick={() => setOpen(true)} aria-label="Mở menu"><Menu /></button><span className="ml-3 font-bold text-ink">AI StudyMate</span></header><main className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-9"><Outlet /></main></div></div>;
}
