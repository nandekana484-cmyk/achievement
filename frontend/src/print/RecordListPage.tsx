// 生産記録票の印刷用の一覧(現場の画面)。1組(1回目と2回目)で1行。ライン、キッティングNo.、ロットNo.で絞り込む。
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useI18n } from "../i18n/I18nProvider";
import { LanguageSwitch } from "../i18n/LanguageSwitch";
import { api } from "../shared/api";
import { lineName } from "../shared/lineName";
import { Notice } from "../shared/Notice";
import { useMasters } from "../shared/useMasters";
import { completedText, filterQuery, linesText, type RecordRow, recordUrl } from "./recordList";

export function RecordListPage() {
  const { t } = useI18n();
  const [params] = useSearchParams();
  const { masters } = useMasters();
  const [line, setLine] = useState(params.get("line") ?? "");
  const [kitting, setKitting] = useState("");
  const [lot, setLot] = useState("");
  const [rows, setRows] = useState<RecordRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const timer = window.setTimeout(() => {
      api.GET("/api/production-records", { params: { query: filterQuery({ line, kitting, lot }) } })
        .then(({ data, error: e }) => {
          if (!alive) return;
          if (data) { setRows(data); setError(null); }
          else setError(typeof e?.detail === "string" ? e.detail : t("record.loadError"));
        })
        .catch(() => alive && setError(t("error.connection")));
    }, 200);
    return () => { alive = false; window.clearTimeout(timer); };
  }, [line, kitting, lot, t]);

  return (
    <main className="record-list">
      <div className="dashboard-head">
        <h1>{t("record.listTitle")}</h1>
        <LanguageSwitch />
      </div>
      <p>{t("record.listHint")}</p>
      <div className="record-filters">
        <label>{t("record.filterLine")}
          <select value={line} onChange={(e) => setLine(e.target.value)}>
            <option value="">{t("record.allLines")}</option>
            {masters?.lines.map((l) => <option key={l.line_code} value={l.line_code}>{lineName(l, t)}</option>)}
          </select>
        </label>
        <label>{t("record.filterKitting")}<input value={kitting} onChange={(e) => setKitting(e.target.value)} autoComplete="off" /></label>
        <label>{t("record.filterLot")}<input value={lot} onChange={(e) => setLot(e.target.value)} autoComplete="off" /></label>
        <Link to={line ? `/field/lines/${encodeURIComponent(line)}` : "/field"} className="btn">{t("record.backToLine")}</Link>
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      {rows && rows.length === 0 && !error && <p className="placeholder">{t("record.empty")}</p>}
      {rows && rows.length > 0 && (
        <table className="record-table" aria-label={t("record.listTitle")}>
          <thead>
            <tr>
              <th>{t("record.colCompleted")}</th><th>{t("record.colKitting")}</th><th>{t("record.colLine")}</th>
              <th>{t("record.colLots")}</th><th>{t("record.colProduct")}</th><th />
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.kitting_no}>
                <td>{completedText(r.completed_at)}</td>
                <td>
                  {r.side1_kitting_no && <div>{r.side1_kitting_no}{r.side1_completed ? "" : " (1)"}</div>}
                  {r.side2_kitting_no && <div>{r.side2_kitting_no}{r.side2_completed ? "" : " (2)"}</div>}
                  {r.side2_unlinked && <span className="record-flag">{t("record.noLink")}</span>}
                </td>
                <td>{linesText(r)}</td>
                <td>{r.lot_nos.join(t("common.listSeparator"))}</td>
                <td>{r.product_name}</td>
                <td><Link className="btn btn-primary" to={recordUrl(r.kitting_no, line)}>{t("record.open")}</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
