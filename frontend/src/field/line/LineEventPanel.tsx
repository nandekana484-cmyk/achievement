// 右のパネルの下: 付帯作業。計画を選んでいなくても使える。終了していないものは経過時間と終了ボタンを出す。
import { forwardRef } from "react";
import { useI18n } from "../../i18n/I18nProvider";
import { localName } from "../../i18n/translate";
import type { LineEvent, Reason } from "../../shared/api";
import { formatElapsed, formatHM } from "./timeScale";

type Props = {
  reasons: Reason[];
  openEvents: LineEvent[];
  nowMs: number;
  isBusy: (key: string) => boolean;
  onStart: (reason: Reason) => void;
  onEnd: (event: LineEvent) => void;
};

export const LineEventPanel = forwardRef<HTMLElement, Props>(function LineEventPanel(
  { reasons, openEvents, nowMs, isBusy, onStart, onEnd }, ref,
) {
  const { t, lang } = useI18n();
  const openReasonIds = new Set(openEvents.map((e) => e.reason_id));
  return (
    <section className="line-event-panel" ref={ref} aria-label={t("lineEvent.title")}>
      <h2 className="panel-title">{t("lineEvent.title")}</h2>
      {openEvents.length > 0 && (
        <ul className="open-events">
          {openEvents.map((e) => (
            <li key={e.id} className="open-event">
              <span className="badge badge-doing">{t("common.doing")}</span>
              <span className="open-event-name">
                {localName(lang, e.reason_name, e.reason_name_vi)}
                {e.equipment_name ? t("lineEvent.withEquipment", { name: localName(lang, e.equipment_name, e.equipment_name_vi) }) : ""}
                {e.reason_text ? t("lineEvent.withText", { text: e.reason_text }) : ""}
              </span>
              <span className="open-event-time">
                {t("lineEvent.since", { time: formatHM(e.start_at), elapsed: formatElapsed(Date.parse(e.start_at), nowMs, t) })}
              </span>
              <button type="button" className="btn btn-end" disabled={isBusy(`lineEventEnd:${e.id}`)} onClick={() => onEnd(e)}>
                {isBusy(`lineEventEnd:${e.id}`) ? t("common.sending") : t("common.end")}
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="reason-grid">
        {reasons.map((r) => (
          <button
            key={r.id}
            type="button"
            className="btn reason-button"
            disabled={openReasonIds.has(r.id) || isBusy(`lineEventStart:${r.id}`)}
            onClick={() => onStart(r)}
          >
            {localName(lang, r.name, r.name_vi)}
            {openReasonIds.has(r.id) && <span className="reason-note">{t("common.doing")}</span>}
          </button>
        ))}
      </div>
    </section>
  );
});
