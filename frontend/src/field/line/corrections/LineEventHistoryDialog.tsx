// 付帯作業の訂正の履歴(ラインと稼働日。新しい順)と、その日の付帯作業の一覧(取り消したものは取り消し線)。見るだけ。
import { useI18n } from "../../../i18n/I18nProvider";
import { localName } from "../../../i18n/translate";
import { api, type LineEvent } from "../../../shared/api";
import { Dialog } from "../../../shared/Dialog";
import { formatHM, formatMD } from "../timeScale";
import { CorrectionList, useCorrections } from "./CorrectionList";

type Props = { lineCode: string; date: string; events: LineEvent[]; onClose: () => void };

export function LineEventHistoryDialog({ lineCode, date, events, onClose }: Props) {
  const { t, lang } = useI18n();
  const corrections = useCorrections(() =>
    api.GET("/api/lines/{line_code}/corrections", { params: { path: { line_code: lineCode }, query: { date } } }));
  return (
    <Dialog title={t("history.lineEventsTitle", { date: formatMD(date) })} wide onCancel={onClose} cancelLabel={t("common.close")}>
      <h3 className="fix-section-title">{t("history.records")}</h3>
      {events.length === 0 ? <p className="fix-note">{t("history.noRecords")}</p> : (
        <ul className="record-list" aria-label={t("history.records")}>
          {events.map((e) => (
            <li key={e.id} className={`record-row${e.voided_at ? " record-voided" : ""}`}>
              <span className="record-main">
                <span className="record-label">{localName(lang, e.reason_name, e.reason_name_vi)}</span>
                <span className="record-time">{e.end_at ? t("step.timeRange", { start: formatHM(e.start_at), end: formatHM(e.end_at) })
                  : t("step.timeOpen", { start: formatHM(e.start_at) })}</span>
              </span>
              {e.voided_at && <span className="badge badge-void">{t("history.voided")}</span>}
            </li>
          ))}
        </ul>
      )}
      <h3 className="fix-section-title">{t("history.corrections")}</h3>
      <CorrectionList {...corrections} />
    </Dialog>
  );
}
