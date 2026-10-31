// 日報(画面で見るときも、印刷と同じ A4 横向きの形)。最上部の見出し、上段・下段のガントチャート、凡例。
// 行が多いときは次のページに続け、見出しを繰り返す。色だけで区別しないよう、棒の中に工程の略称を出す。
import { STEP_COLORS } from "../../field/line/steps";
import type { StepType } from "../../shared/api";
import { type AdminKey, at } from "../messages";
import { efficiencyText, excludedText } from "./efficiency";
import { barBox, type DailyReport, formatDateTime, formatTime, type Half, hourTicks, paginate, type ReportRow } from "./gantt";

const STEPS: StepType[] = ["setup", "n1_check", "production", "first_article", "xray", "cleanup"];
const LINE_EVENT_COLOR = "#bf8700";
const short = (s: string) => at(`step.short.${s}` as AdminKey);

export function DailyReportView({ report }: { report: DailyReport }) {
  const pages = paginate(report.rows);
  return (
    <div className="report-pages">
      {pages.map((rows, i) => (
        <section key={i} className="report-sheet" aria-label={at("report.page", { page: i + 1, pages: pages.length })}>
          <ReportHeader report={report} page={i + 1} pages={pages.length} />
          {report.rows.length === 0 && <p className="report-empty">{at("report.empty")}</p>}
          {report.halves.map((half, h) => <HalfChart key={h} half={half} index={h} rows={rows} />)}
        </section>
      ))}
    </div>
  );
}

function ReportHeader({ report, page, pages }: { report: DailyReport; page: number; pages: number }) {
  return (
    <header className="report-head">
      <h2 className="report-title">{at("report.heading")}</h2>
      <span>{at("report.line", { name: report.line.name, code: report.line.line_code })}</span>
      <span>{at("report.workday", { date: report.date, start: formatTime(report.workday_start), end: formatTime(report.workday_end) })}</span>
      <span className="report-total">{at("report.producedTotal", { qty: report.produced_total })}</span>
      <span className="report-total">{at("report.ngTotal", { qty: report.ng_total })}</span>
      <span className="report-total">{efficiencyText(report)}</span>
      {excludedText(report) && <span className="report-excluded">{excludedText(report)}</span>}
      <span className="report-generated">{at("report.generatedAt", { time: formatDateTime(report.generated_at) })}</span>
      <span className="report-pageno">{at("report.page", { page, pages })}</span>
      <Legend />
    </header>
  );
}

function Legend() {
  return (
    <div className="report-legend" aria-label={at("report.legend")}>
      <span>{at("report.legend")}:</span>
      {STEPS.map((s) => (
        <span key={s} className="report-legend-item">
          <span className="report-swatch" style={{ background: STEP_COLORS[s] }}>{short(s)}</span>
          {at(`step.${s}` as AdminKey)}
        </span>
      ))}
      <span className="report-legend-item">
        <span className="report-swatch" style={{ background: LINE_EVENT_COLOR }}>{at("report.lineEvents")}</span>
      </span>
      <span className="report-legend-item"><span className="report-swatch report-swatch-open">{at("report.open")}</span></span>
    </div>
  );
}

function HalfChart({ half, index, rows }: { half: Half; index: number; rows: ReportRow[] }) {
  const ticks = hourTicks(half);
  const title = at(index === 0 ? "report.upper" : "report.lower", { start: ticks[0].label, end: ticks[ticks.length - 1].label });
  return (
    <div className="report-half" role="table" aria-label={title}>
      <div className="report-axis" role="row">
        <span className="report-rowhead" role="columnheader">{title}</span>
        <span className="report-track">
          {ticks.map((t) => <span key={t.left} className="report-tick" style={{ left: `${t.left}%` }}>{t.label}</span>)}
        </span>
      </div>
      {rows.map((row) => (
        <div key={row.kitting_no ?? "line-events"} className={`report-row${row.kind === "line_event" ? " report-row-events" : ""}`} role="row">
          <span className="report-rowhead" role="rowheader">
            {row.kind === "line_event" ? at("report.lineEvents") : <><b>{row.kitting_no}</b><small>{row.product_names}</small></>}
          </span>
          <span className="report-track">
            {ticks.map((t) => <span key={t.left} className="report-grid" style={{ left: `${t.left}%` }} />)}
            {row.bars.filter((b) => b.half === index).map((b, i) => <Bar key={i} bar={b} half={half} />)}
          </span>
        </div>
      ))}
    </div>
  );
}

function Bar({ bar, half }: { bar: ReportRow["bars"][number]; half: Half }) {
  const { left, width } = barBox(bar, half);
  const text = bar.step_type ? short(bar.step_type) : bar.label;
  const color = bar.step_type ? STEP_COLORS[bar.step_type as StepType] : LINE_EVENT_COLOR;
  if (!bar.step_type) {
    // 付帯作業は短いことが多いので、理由は棒の下に出す(棒の中では切れてしまうため)
    return (
      <span className={`report-event${bar.open ? " report-open" : ""}`} style={{ left: `${left}%`, width: `${width}%` }}>
        <span className="report-event-bar" style={{ background: color }} />
        <span className="report-event-label">{text}</span>
      </span>
    );
  }
  return (
    <span className={`report-bar${bar.open ? " report-open" : ""}`} title={bar.label}
      style={{ left: `${left}%`, width: `${width}%`, background: color }}>
      {text}
    </span>
  );
}
