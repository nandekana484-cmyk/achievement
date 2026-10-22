// 管理画面の「日報」: ラインと稼働日を選んで日報を出す(印刷はブラウザの印刷プレビュー)。区間の CSV もここから出す。
import { useCallback, useEffect, useState } from "react";
import { adminApi, type LineRow, useAdminCall } from "../adminApi";
import { at } from "../messages";
import { Feedback, useAdminList } from "../parts";
import { DailyReportView } from "./DailyReportView";
import type { DailyReport } from "./gantt";

const loadLines = () => adminApi.GET("/api/admin/lines");

/** サーバーの今の稼働日(8:15 より前なら前の日)。ブラウザの日付は使わない。 */
function useServerWorkday(): string | null {
  const call = useAdminCall();
  const [workday, setWorkday] = useState<string | null>(null);
  useEffect(() => {
    void call(() => adminApi.GET("/api/admin/me")).then((r) => r.ok && setWorkday(r.data.workday));
  }, [call]);
  return workday;
}

export function ReportsPage() {
  const workday = useServerWorkday();
  if (!workday) return <p className="admin-loading">{at("loading")}</p>;
  return <ReportsContent workday={workday} />;
}

function ReportsContent({ workday }: { workday: string }) {
  const call = useAdminCall();
  const { rows: lines, error: linesError } = useAdminList<LineRow>(loadLines);
  const [lineCode, setLineCode] = useState("");
  const [date, setDate] = useState(workday);
  const [report, setReport] = useState<DailyReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!lineCode && lines?.length) setLineCode((lines.find((l) => l.active) ?? lines[0]).line_code);
  }, [lines, lineCode]);

  const show = useCallback(async () => {
    if (!lineCode || !date) return;
    const r = await call(() => adminApi.GET("/api/admin/reports/daily", { params: { query: { date, line_code: lineCode } } }));
    setReport(r.ok ? r.data : null);
    setError(r.ok ? null : r.message);
  }, [call, date, lineCode]);
  useEffect(() => void show(), [show]);

  return (
    <section aria-label={at("reports.title")} className="reports">
      <div className="report-controls">
        <h1>{at("reports.title")}</h1>
        <div className="admin-add">
          <label className="admin-check">{at("reports.line")}
            <select aria-label={at("reports.line")} value={lineCode} onChange={(e) => setLineCode(e.target.value)}>
              {lines?.map((l) => <option key={l.line_code} value={l.line_code}>{at("lineOption", { name: l.name, code: l.line_code })}</option>)}
            </select>
          </label>
          <label className="admin-check">{at("reports.date")}
            <input type="date" aria-label={at("reports.date")} value={date} onChange={(e) => setDate(e.target.value)} />
          </label>
          <button type="button" className="admin-btn" onClick={() => void show()}>{at("reports.show")}</button>
          <button type="button" className="admin-btn admin-primary" disabled={!report} onClick={() => window.print()}>{at("reports.print")}</button>
          <span className="admin-note">{at("reports.printNote")}</span>
        </div>
        <Feedback error={error ?? linesError} />
        <CsvExport lines={lines ?? []} defaultDate={workday} />
      </div>
      {report && <div className="report-preview"><DailyReportView report={report} /></div>}
    </section>
  );
}

function filenameOf(response: Response): string {
  const m = /filename="([^"]+)"/.exec(response.headers.get("content-disposition") ?? "");
  return m ? m[1] : "intervals.csv";
}

function CsvExport({ lines, defaultDate }: { lines: LineRow[]; defaultDate: string }) {
  const call = useAdminCall();
  const [from, setFrom] = useState(defaultDate);
  const [to, setTo] = useState(defaultDate);
  const [lineCode, setLineCode] = useState<string>("");
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const download = async () => {
    let name = "intervals.csv";
    const r = await call(async () => {
      const res = await adminApi.GET("/api/admin/reports/intervals.csv", {
        params: { query: { from, to, line_code: lineCode || undefined } }, parseAs: "blob",
      });
      name = filenameOf(res.response);
      return res;
    });
    if (!r.ok) return setMessage({ ok: false, text: r.message });
    // ブラウザに保存させる(ファイル名はサーバーが付けた、期間とラインの入ったもの)
    const url = URL.createObjectURL(r.data as Blob);
    const a = Object.assign(document.createElement("a"), { href: url, download: name });
    a.click();
    URL.revokeObjectURL(url);
    setMessage({ ok: true, text: at("reports.downloaded", { name }) });
  };

  return (
    <div className="report-csv">
      <h2>{at("reports.csvTitle")}</h2>
      <p className="admin-note">{at("reports.csvNote")}</p>
      <div className="admin-add">
        <label className="admin-check">{at("reports.from")}
          <input type="date" aria-label={at("reports.from")} value={from} onChange={(e) => setFrom(e.target.value)} />
        </label>
        <label className="admin-check">{at("reports.to")}
          <input type="date" aria-label={at("reports.to")} value={to} onChange={(e) => setTo(e.target.value)} />
        </label>
        <select aria-label={at("reports.line")} value={lineCode} onChange={(e) => setLineCode(e.target.value)}>
          <option value="">{at("reports.allLines")}</option>
          {lines.map((l) => <option key={l.line_code} value={l.line_code}>{at("lineOption", { name: l.name, code: l.line_code })}</option>)}
        </select>
        <button type="button" className="admin-btn admin-primary" disabled={!from || !to} onClick={() => void download()}>
          {at("reports.download")}
        </button>
      </div>
      <Feedback message={message} />
    </div>
  );
}
