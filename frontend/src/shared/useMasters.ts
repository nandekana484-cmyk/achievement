// マスタ(ライン・作業者・設備・理由)を読むフック。lineCode を渡すと、設備はそのラインのものだけ。
import { useEffect, useState } from "react";
import { api, type Masters } from "./api";

export function useMasters(lineCode?: string): { masters: Masters | null; error: string | null } {
  const [masters, setMasters] = useState<Masters | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .GET("/api/masters", { params: { query: lineCode ? { line_code: lineCode } : {} } })
      .then(({ data, error: e }) => {
        if (!alive) return;
        if (data) setMasters(data);
        else setError(typeof e?.detail === "string" ? e.detail : "マスタを読めませんでした");
      })
      .catch(() => alive && setError("通信できませんでした。電波の状態を確かめてください"));
    return () => {
      alive = false;
    };
  }, [lineCode]);

  return { masters, error };
}
