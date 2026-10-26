import { Calendar, Mail, Shield, UserRound } from "lucide-react";
import { useAuth } from "../auth/AuthProvider";
import { Badge, cardClass, PageHeader } from "../components/ui";

export function ProfilePage() {
  const { user } = useAuth();
  const fields = [["Tên đăng nhập", user?.username, UserRound], ["Email", user?.email, Mail], ["Vai trò", user?.role, Shield], ["Tham gia", user ? new Date(user.created_at).toLocaleDateString("vi-VN") : "", Calendar]] as const;
  return <><PageHeader eyebrow="Account" title="Hồ sơ cá nhân" description="Thông tin tài khoản được đọc từ endpoint /users/me." /><section className={`${cardClass} mx-auto max-w-2xl`}><div className="flex items-center gap-4 border-b pb-6"><div className="grid h-16 w-16 place-items-center rounded-2xl bg-gradient-to-br from-ocean to-mint text-2xl font-black text-white">{user?.full_name.charAt(0).toUpperCase()}</div><div><h2 className="text-xl font-bold text-ink">{user?.full_name}</h2><div className="mt-1"><Badge tone={user?.is_active ? "green" : "red"}>{user?.is_active ? "Đang hoạt động" : "Đã khóa"}</Badge></div></div></div><dl className="mt-6 grid gap-4 sm:grid-cols-2">{fields.map(([label, value, Icon]) => <div key={label} className="rounded-xl bg-slate-50 p-4"><dt className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-400"><Icon className="h-4 w-4" />{label}</dt><dd className="mt-2 font-semibold text-ink">{value}</dd></div>)}</dl><p className="mt-6 rounded-xl bg-blue-50 p-4 text-sm text-blue-800">Backend hiện chưa có endpoint cập nhật hồ sơ, vì vậy trang này chỉ hiển thị dữ liệu và không tạo chức năng chỉnh sửa giả.</p></section></>;
}
