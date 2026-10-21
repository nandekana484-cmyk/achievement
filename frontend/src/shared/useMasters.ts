// マスタ(ライン・作業者・設備・理由)を読むフック。lineCode を渡すと、設備はそのラインのものだけ。
import { useEffect, useRef, useState } from "react";
import { useI18n } from "../i18n/I18nProvider";
import { api, type Masters } from "./api";

export function useMasters(lineCode?: string): { masters: Masters | null; error: string | null } {
  const [masters, setMasters] = useState<Masters | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { t: translate } = useI18n();
  const t = useRef(translate); // 言語を切り替えても読み直さない(失敗の文はその時点の言語)
  t.current = translate;

  useEffect(() => {
    let alive = true;
    api
      .GET("/api/masters", { params: { query: lineCode ? { line_code: lineCode } : {} } })
      .then(({ data, error: e }) => {
        if (!alive) return;
        if (data) setMasters(data);
        else setError(typeof e?.detail === "string" ? e.detail : t.current("error.mastersLoad"));
      })
      .catch(() => alive && setError(t.current("error.connection")));
    return () => {
      alive = false;
    };
  }, [lineCode]);

  return { masters, error };
}
