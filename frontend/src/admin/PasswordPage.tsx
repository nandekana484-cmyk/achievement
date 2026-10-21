// 自分のパスワードの変更(今のパスワードが要る。8文字以上)。
import { type FormEvent, useState } from "react";
import { adminApi } from "./adminApi";
import { at } from "./messages";
import { Feedback, useSave } from "./parts";

export function PasswordPage() {
  const { save, message } = useSave(() => undefined);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [mismatch, setMismatch] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setMismatch(next !== confirm);
    if (next !== confirm) return;
    const body = { current_password: current, new_password: next };
    if (await save(() => adminApi.PUT("/api/admin/password", { body }), at("password.changed"))) {
      setCurrent("");
      setNext("");
      setConfirm("");
    }
  };

  return (
    <section aria-label={at("password.title")}>
      <h1>{at("password.title")}</h1>
      {mismatch ? <p className="admin-error" role="alert">{at("password.mismatch")}</p> : <Feedback message={message} />}
      <form className="admin-card admin-password" onSubmit={submit}>
        <label>{at("password.current")}<input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" required /></label>
        <label>{at("password.new")}<input type="password" value={next} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" minLength={8} required /></label>
        <label>{at("password.confirm")}<input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" minLength={8} required /></label>
        <button type="submit" className="admin-btn admin-primary">{at("save")}</button>
      </form>
    </section>
  );
}
