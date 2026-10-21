// ボタン操作を送るフック。送信中のボタンを押せなくし、失敗の理由を出し、成功したら onSuccess を呼ぶ。
import { useCallback, useRef, useState } from "react";
import { useI18n } from "../i18n/I18nProvider";
import { type ApiResult, failureMessage, RequestIdStore, sendWithRetry } from "./send";

export type RunResult<T> = { ok: true; data: T } | { ok: false; message: string };

/** showError: false にすると、失敗の理由を画面のお知らせに出さない(ダイアログの中に出すとき)。 */
export type RunOptions = { showError?: boolean };

export type Operation = {
  /** key は操作の種類(例: "step:計画:工程")。payload が同じあいだは同じ request_id で送る。 */
  run: <T>(
    key: string, payload: unknown, call: (requestId: string) => Promise<ApiResult<T>>, options?: RunOptions,
  ) => Promise<RunResult<T>>;
  isBusy: (key: string) => boolean;
  error: string | null;
  clearError: () => void;
};

export function useOperation(onSuccess: () => void): Operation {
  const store = useRef(new RequestIdStore());
  const busyRef = useRef(new Set<string>());
  const [busy, setBusy] = useState<ReadonlySet<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const { t } = useI18n();

  const run = useCallback(
    async <T,>(key: string, payload: unknown, call: (requestId: string) => Promise<ApiResult<T>>, options: RunOptions = {}) => {
      if (busyRef.current.has(key)) return { ok: false, message: t("error.stillSending") } as RunResult<T>;
      busyRef.current.add(key);
      setBusy(new Set(busyRef.current));
      setError(null);
      const requestId = store.current.idFor(key, payload);
      const outcome = await sendWithRetry(() => call(requestId));
      busyRef.current.delete(key);
      setBusy(new Set(busyRef.current));
      if (!outcome.ok) {
        const message = failureMessage(outcome, t);
        if (options.showError !== false) setError(message);
        return { ok: false, message } as RunResult<T>;
      }
      store.current.succeeded(key);
      onSuccess();
      return { ok: true, data: outcome.data } as RunResult<T>;
    },
    [onSuccess, t],
  );

  return { run, isBusy: (key) => busy.has(key), error, clearError: () => setError(null) };
}
