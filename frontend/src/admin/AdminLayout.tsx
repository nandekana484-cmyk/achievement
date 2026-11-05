// 管理画面の枠: 左にメニュー、右に内容。開いたときにログイン中かを確かめ、ログインしていなければログイン画面に戻す。
import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { type AdminMe, adminApi, useAdminCall } from "./adminApi";
import { at } from "./messages";
import { ct } from "./messagesControlSheet";

const MENU: [string, () => string][] = [
  ["reports", () => at("menu.reports")],
  ["actuals", () => at("menu.actuals")],
  ["equipment", () => at("menu.equipment")],
  ["reasons", () => at("menu.reasons")],
  ["lines", () => at("menu.lines")],
  ["operators", () => at("menu.operators")],
  ["access", () => at("menu.access")],
  ["teitori", () => at("menu.teitori")],
  ["handover", () => at("menu.handover")],
  ["open-runs", () => at("menu.openRuns")],
  ["control-sheets", () => ct("menu.controlSheets")],
  ["password", () => at("menu.password")],
];

export function AdminLayout() {
  const call = useAdminCall();
  const navigate = useNavigate();
  const [me, setMe] = useState<AdminMe | null>(null);

  useEffect(() => {
    void call(() => adminApi.GET("/api/admin/me")).then((r) => r.ok && setMe(r.data));
  }, [call]);

  const logout = async () => {
    await call(() => adminApi.POST("/api/admin/logout"));
    navigate("/admin/login", { replace: true });
  };

  if (!me) return <p className="admin-loading">{at("loading")}</p>;
  return (
    <div className="admin">
      <nav className="admin-menu" aria-label={at("title")}>
        <p className="admin-title">{at("title")}</p>
        <p className="admin-user">{at("menu.user", { name: me.name, id: me.worker_id ?? "" })}</p>
        {MENU.map(([path, label]) => (
          <NavLink key={path} to={`/admin/${path}`} className={({ isActive }) => `admin-menu-item${isActive ? " admin-menu-current" : ""}`}>
            {label()}
          </NavLink>
        ))}
        <button type="button" className="admin-menu-item admin-logout" onClick={() => void logout()}>{at("menu.logout")}</button>
      </nav>
      <main className="admin-main">
        <Outlet />
      </main>
    </div>
  );
}
