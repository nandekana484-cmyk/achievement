// ダイアログの送信中・失敗の理由の状態。送信が成功したら呼び出し側がダイアログを閉じる。
import { useState } from "react";

export function useSubmit() {
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submit = async (send: () => Promise<string | null>) => {
    setSending(true);
    setError(null);
    const failure = await send();
    setSending(false);
    if (failure) setError(failure);
  };
  return { sending, error, submit };
}
