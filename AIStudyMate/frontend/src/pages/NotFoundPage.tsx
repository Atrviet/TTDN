import { Link } from "react-router-dom";
import { buttonClass } from "../components/ui";
export function NotFoundPage() { return <div className="grid min-h-[70vh] place-items-center text-center"><div><p className="text-7xl font-black text-blue-100">404</p><h1 className="mt-3 text-2xl font-bold text-ink">Không tìm thấy trang</h1><Link className={`${buttonClass} mt-6`} to="/">Về tổng quan</Link></div></div>; }
