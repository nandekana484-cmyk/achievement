// ボタン操作を送るフック。送信中のボタンを押せなくし、失敗の理由を画面に出し、成功したら onSuccess を呼ぶ。
import { useCallback, useRef, useState } from "react";
import { type ApiResult, RequestIdStore, sendWithRetry } from "./send";

export type Operation = {
  /** key は操作の種類(例: "start:計画:工程")。payload が同じあいだは同じ request_id で送る。 */
  run: <T>(key: string, payload: unknown, call: (requestId: string) => Promise<ApiResult<T>>) => Promise<T | undefined>;
  isBusy: (key: string) => boolean;
  error: string | null;
  clearError: () => void;
};

export function useOperation(onSuccess: () => void): Operation {
  const store = useRef(new RequestIdStore());
  const busyRef = useRef(new Set<string>());
  const [busy, setBusy] = useState<ReadonlySet<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(
    async <T,>(key: string, payload: unknown, call: (requestId: string) => Promise<ApiResult<T>>) => {
      if (busyRef.current.has(key)) return undefined;
      busyRef.current.add(key);
      setBusy(new Set(busyRef.current));
      setError(null);
      const requestId = store.current.idFor(key, payload);
      const outcome = await sendWithRetry(() => call(requestId));
      busyRef.current.delete(key);
      setBusy(new Set(busyRef.current));
      if (!outcome.ok) {
        setError(outcome.message);
        return undefined;
      }
      store.current.succeeded(key);
      onSuccess();
      return outcome.data;
    },
    [onSuccess],
  );

  return { run, isBusy: (key) => busy.has(key), error, clearError: () => setError(null) };
}
