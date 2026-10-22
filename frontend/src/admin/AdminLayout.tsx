// 管理画面の枠: 左にメニュー、右に内容。開いたときにログイン中かを確かめ、ログインしていなければログイン画面に戻す。
import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { type AdminMe, adminApi, useAdminCall } from "./adminApi";
import { type AdminKey, at } from "./messages";

const MENU: [string, AdminKey][] = [
  ["reports", "menu.reports"],
  ["equipment", "menu.equipment"],
  ["reasons", "menu.reasons"],
  ["lines", "menu.lines"],
  ["operators", "menu.operators"],
  ["password", "menu.password"],
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
        {MENU.map(([path, key]) => (
          <NavLink key={path} to={`/admin/${path}`} className={({ isActive }) => `admin-menu-item${isActive ? " admin-menu-current" : ""}`}>
            {at(key)}
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
