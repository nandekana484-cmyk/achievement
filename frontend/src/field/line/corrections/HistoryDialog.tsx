// 訂正の履歴の画面。計画の記録の一覧(取り消した記録は取り消し線)と、訂正の履歴(新しい順)を出す。見るだけ。
import { useI18n } from "../../../i18n/I18nProvider";
import { api, type BoardPlan, type RunEvent, type StepType } from "../../../shared/api";
import { Dialog } from "../../../shared/Dialog";
import { operatorLabel } from "../operatorLabel";
import { recordLabel, recordNumbers, STEP_LABEL_KEYS } from "../steps";
import { formatHM, formatMDHM } from "../timeScale";
import { CorrectionList, useCorrections } from "./CorrectionList";
import { REASON_KEYS } from "./ReasonPicker";

type Props = { plan: BoardPlan; onClose: () => void };

export function HistoryDialog({ plan, onClose }: Props) {
  const { t } = useI18n();
  const kno = plan.plan.kitting_no;
  const corrections = useCorrections(() =>
    api.GET("/api/runs/{kitting_no}/corrections", { params: { path: { kitting_no: kno } } }));
  const numbers = recordNumbers(plan.events);
  const events = [...plan.events].sort((a, b) => Date.parse(a.start_at) - Date.parse(b.start_at) || a.id - b.id);

  return (
    <Dialog title={t("history.title", { kno })} wide onCancel={onClose} cancelLabel={t("common.close")}>
      <h3 className="fix-section-title">{t("history.records")}</h3>
      {events.length === 0 ? <p className="fix-note">{t("history.noRecords")}</p> : (
        <ul className="record-list" aria-label={t("history.records")}>
          {events.map((e) => <RecordRow key={e.id} e={e} numbers={numbers} />)}
        </ul>
      )}
      <h3 className="fix-section-title">{t("history.corrections")}</h3>
      <CorrectionList {...corrections} />
    </Dialog>
  );
}

function RecordRow({ e, numbers }: { e: RunEvent; numbers: Map<number, number> }) {
  const { t } = useI18n();
  const label = e.voided_at ? t(STEP_LABEL_KEYS[e.step_type as StepType]) : recordLabel(e, numbers, t);
  const time = e.end_at ? t("step.timeRange", { start: formatHM(e.start_at), end: formatHM(e.end_at) })
    : t("step.timeOpen", { start: formatHM(e.start_at) });
  return (
    <li className={`record-row${e.voided_at ? " record-voided" : ""}`}>
      <span className="record-main">
        <span className="record-label">{label}</span>
        <span className="record-time">{time}</span>
        {e.produced_qty != null && <span>{t("unit.sheets", { count: e.produced_qty })}</span>}
      </span>
      {e.added_later && <span className="badge badge-add">{t("history.addedLater")}</span>}
      {e.voided_at && (
        <span className="record-void-note">
          <span className="badge badge-void">{t("history.voided")}</span>
          {t("history.voidedBy", {
            name: operatorLabel(e.voided_by_name ?? "", e.voided_by_worker_id, t),
            time: formatMDHM(e.voided_at),
            reason: t(REASON_KEYS[e.void_reason ?? "other"] ?? "correctionReason.other"),
          })}
        </span>
      )}
    </li>
  );
}
