// 管理画面のログイン(作業者IDとパスワード)。ログインが切れて戻ってきたときは、そのことを出す。
import { type FormEvent, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { adminApi } from "./adminApi";
import { at } from "./messages";

export function AdminLogin() {
  const navigate = useNavigate();
  const expired = (useLocation().state as { expired?: boolean } | null)?.expired;
  const [workerId, setWorkerId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setSending(true);
    setError(null);
    try {
      const { response, error: err } = await adminApi.POST("/api/admin/login", { body: { worker_id: workerId, password } });
      if (response.ok) navigate("/admin/equipment", { replace: true });
      else setError(typeof err === "object" && err && "detail" in err && typeof err.detail === "string" ? err.detail : at("server", { status: response.status }));
    } catch {
      setError(at("network"));
    } finally {
      setSending(false);
    }
  };

  return (
    <main className="admin-login">
      <form className="admin-card" onSubmit={submit} aria-label={at("login.title")}>
        <h1>{at("login.title")}</h1>
        {expired && !error && <p className="admin-info" role="status">{at("login.expired")}</p>}
        {error && <p className="admin-error" role="alert">{error}</p>}
        <label>
          {at("login.workerId")}
          <input value={workerId} onChange={(e) => setWorkerId(e.target.value)} autoComplete="username" autoFocus maxLength={64} required />
        </label>
        <label>
          {at("login.password")}
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" maxLength={256} required />
        </label>
        <button type="submit" className="admin-btn admin-primary" disabled={sending}>{at("login.submit")}</button>
        <Link to="/field" className="admin-sub-link">{at("login.backToField")}</Link>
      </form>
    </main>
  );
}
