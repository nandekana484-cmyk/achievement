// 管理画面の部品: 一覧の読み込み、結果の表示、入力欄、保存の送り方。
import { useCallback, useEffect, useState } from "react";
import { type CallOutcome, useAdminCall } from "./adminApi";
import { at } from "./messages";

type Result<T> = { data?: T; error?: unknown; response: Response };

/** 一覧を読み、変更のあとに読み直す。 */
export function useAdminList<T>(load: () => Promise<Result<T[]>>) {
  const call = useAdminCall();
  const [rows, setRows] = useState<T[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reload = useCallback(() => {
    void call(load).then((r) => (r.ok ? setRows(r.data) : setError(r.message)));
  }, [call, load]);
  useEffect(reload, [reload]);
  return { rows, error, reload };
}

/** 保存などを送り、結果(成功・失敗の理由)を画面に出す。成功したら一覧を読み直す。 */
export function useSave(reload: () => void) {
  const call = useAdminCall();
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const save = async <T,>(send: () => Promise<Result<T>>, okText = at("saved")): Promise<boolean> => {
    const r: CallOutcome<T> = await call(send);
    setMessage(r.ok ? { ok: true, text: okText } : { ok: false, text: r.message });
    if (r.ok) reload();
    return r.ok;
  };
  return { save, message };
}

export function Feedback({ message, error }: { message?: { ok: boolean; text: string } | null; error?: string | null }) {
  if (error) return <p className="admin-error" role="alert">{error}</p>;
  if (!message) return null;
  return <p className={message.ok ? "admin-info" : "admin-error"} role={message.ok ? "status" : "alert"}>{message.text}</p>;
}

export function TextInput({ value, onChange, label, required }: { value: string; onChange: (v: string) => void; label: string; required?: boolean }) {
  return <input aria-label={label} placeholder={label} value={value} maxLength={100} required={required} onChange={(e) => onChange(e.target.value)} />;
}

export function NumberInput({ value, onChange, label }: { value: number; onChange: (v: number) => void; label: string }) {
  return <input aria-label={label} type="number" className="admin-num" value={value} onChange={(e) => onChange(Number(e.target.value))} />;
}

export function Check({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return <input aria-label={label} type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />;
}

export const yesNo = (v: boolean) => (v ? at("yes") : at("no"));
export const stateText = (active: boolean) => (active ? at("active") : at("inactive"));
