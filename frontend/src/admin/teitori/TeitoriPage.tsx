// 丁取り: 丁取りが引けない計画の一覧(見るだけ)。効率の計算から外れる計画。詳細: docs/design/metrics.md
import { useCallback, useEffect, useState } from "react";
import type { components } from "../../api/schema";
import { adminApi, useAdminCall } from "../adminApi";
import { at } from "../messages";
import { reasonLabel } from "../reports/efficiency";

type Unresolved = components["schemas"]["UnresolvedOut"];

export function TeitoriPage() {
  const call = useAdminCall();
  const [data, setData] = useState<Unresolved | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => {
    void call(() => adminApi.GET("/api/admin/teitori/unresolved")).then((r) => (r.ok ? setData(r.data) : setError(r.message)));
  }, [call]);
  useEffect(load, [load]);

  if (!data) return <p className="admin-loading">{error ?? at("loading")}</p>;
  return (
    <section aria-label={at("teitori.title")}>
      <h1>{at("teitori.title")}</h1>
      <p className="admin-note">{at("teitori.note")}</p>
      <p>
        {at("teitori.summary", { total: data.total_plans, count: data.unresolved })}
        {Object.entries(data.by_status).length > 0 && (
          <span>
            {at("teitori.byStatusList", {
              items: Object.entries(data.by_status).map(([s, n]) => at("teitori.byStatus", { reason: reasonLabel(s), count: n })).join(at("listSeparator")),
            })}
          </span>
        )}
      </p>
      {data.truncated && <p className="admin-note">{at("teitori.truncated", { limit: data.plans.length })}</p>}
      {data.plans.length === 0 ? (
        <p>{at("teitori.empty")}</p>
      ) : (
        <table className="admin-table">
          <thead>
            <tr>
              <th>{at("teitori.col.kitting")}</th><th>{at("teitori.col.file")}</th><th>{at("teitori.col.line")}</th><th>{at("teitori.col.status")}</th>
            </tr>
          </thead>
          <tbody>
            {data.plans.map((p) => (
              <tr key={p.kitting_no}>
                <td>{p.kitting_no}</td><td>{p.file_no}</td><td>{p.line_code}</td>
                <td>{reasonLabel(p.status)}<span className="admin-code"> ({p.status})</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
