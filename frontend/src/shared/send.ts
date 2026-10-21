// ボタン操作の送り方(開発指針 0-5)。画面から切り離した処理なので、vitest でテストする。
import type { Translate } from "../i18n/translate";
import { uuidv4 } from "./uuid";

/** openapi-fetch の応答のうち、ここで使う部分。 */
export type ApiResult<T> = { data?: T; error?: unknown; response: Response };

/** 失敗。detail はサーバーが返した理由の文(503・409・404。訳さずにそのまま出す)。 */
export type SendFailure = { ok: false; status: number | null; detail: string | null; retryable: boolean };

export type SendOutcome<T> = { ok: true; data: T } | SendFailure;

/** 失敗を画面に出す文。サーバーの理由の文があればそのまま、無ければ選んだ言語の決まった文。 */
export function failureMessage(f: Pick<SendFailure, "status" | "detail">, t: Translate): string {
  if (f.detail) return f.detail;
  if (f.status === null) return t("error.network");
  if (f.status === 503) return t("error.busy");
  if (f.status === 422) return t("error.invalid");
  return t("error.server", { status: f.status });
}

function detailOf(error: unknown): string | null {
  if (error && typeof error === "object" && "detail" in error) {
    const detail = (error as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return null;
}

function failure(status: number | null, error: unknown): SendFailure {
  const withDetail = status === 503 || status === 409 || status === 404;
  return { ok: false, status, detail: withDetail ? detailOf(error) : null, retryable: status === null || status === 503 };
}

/**
 * 1回送り、通信の失敗と 503 のときだけ、同じ呼び出し(同じ request_id)で retries 回まで送り直す。
 * 409・404 は送り直さず、応答の detail をそのまま返す。
 */
export async function sendWithRetry<T>(call: () => Promise<ApiResult<T>>, retries = 1): Promise<SendOutcome<T>> {
  let last: SendOutcome<T> = failure(null, null);
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const r = await call();
      if (r.response.ok) return { ok: true, data: r.data as T };
      last = failure(r.response.status, r.error);
    } catch {
      last = failure(null, null);
    }
    if (!last.ok && !last.retryable) return last;
  }
  return last;
}

/**
 * 操作ごとの request_id。成功するまで、同じ操作・同じ内容なら同じ値を返す(内容が変われば作り直す)。
 */
export class RequestIdStore {
  private pending = new Map<string, { payload: string; id: string }>();

  constructor(private readonly newId: () => string = uuidv4) {}

  idFor(key: string, payload: unknown): string {
    const body = JSON.stringify(payload ?? null);
    const cur = this.pending.get(key);
    if (cur && cur.payload === body) return cur.id;
    const id = this.newId();
    this.pending.set(key, { payload: body, id });
    return id;
  }

  succeeded(key: string): void {
    this.pending.delete(key);
  }
}
