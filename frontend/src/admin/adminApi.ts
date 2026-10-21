// 管理画面のAPIクライアント。データを変える要求に決まったヘッダー(X-Genba-Admin: 1)を付ける(サーバーが求める)。
// ログインしていない・切れたとき(401)は、ログイン画面に戻す。
import createClient from "openapi-fetch";
import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import type { components, paths } from "../api/schema";
import { at } from "./messages";

export const adminApi = createClient<paths>({ baseUrl: "", headers: { "X-Genba-Admin": "1" } });

type Schemas = components["schemas"];
export type EquipmentRow = Schemas["EquipmentAdminOut"];
export type ReasonRow = Schemas["ReasonAdminOut"];
export type LineRow = Schemas["LineAdminOut"];
export type OperatorRow = Schemas["OperatorAdminOut"];
export type AdminMe = Schemas["AdminMeOut"];

type Result<T> = { data?: T; error?: unknown; response: Response };
export type CallOutcome<T> = { ok: true; data: T } | { ok: false; message: string };

function detailOf(error: unknown): string | null {
  const detail = error && typeof error === "object" && "detail" in error ? (error as { detail: unknown }).detail : null;
  return typeof detail === "string" ? detail : null;
}

/** API を呼び、401 ならログイン画面に戻す。失敗の理由はサーバーの文をそのまま返す。 */
export function useAdminCall() {
  const navigate = useNavigate();
  return useCallback(async <T,>(send: () => Promise<Result<T>>): Promise<CallOutcome<T>> => {
    try {
      const r = await send();
      if (r.response.status === 401) {
        navigate("/admin/login", { replace: true, state: { expired: true } });
        return { ok: false, message: detailOf(r.error) ?? at("login.expired") };
      }
      if (!r.response.ok) return { ok: false, message: detailOf(r.error) ?? at("server", { status: r.response.status }) };
      return { ok: true, data: r.data as T };
    } catch {
      return { ok: false, message: at("network") };
    }
  }, [navigate]);
}
