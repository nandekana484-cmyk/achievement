// 右のパネルの下: 付帯作業。計画を選んでいなくても使える。終了していないものは経過時間と終了ボタンを出す。
import { forwardRef } from "react";
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
  const openReasonIds = new Set(openEvents.map((e) => e.reason_id));
  return (
    <section className="line-event-panel" ref={ref} aria-label="付帯作業">
      <h2 className="panel-title">付帯作業</h2>
      {openEvents.length > 0 && (
        <ul className="open-events">
          {openEvents.map((e) => (
            <li key={e.id} className="open-event">
              <span className="badge badge-doing">作業中</span>
              <span className="open-event-name">
                {e.reason_name}
                {e.equipment_name ? `(${e.equipment_name})` : ""}
                {e.reason_text ? `:${e.reason_text}` : ""}
              </span>
              <span className="open-event-time">
                {formatHM(e.start_at)} 〜(経過 {formatElapsed(Date.parse(e.start_at), nowMs)})
              </span>
              <button type="button" className="btn btn-end" disabled={isBusy(`lineEventEnd:${e.id}`)} onClick={() => onEnd(e)}>
                {isBusy(`lineEventEnd:${e.id}`) ? "送信中…" : "終了"}
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
            {r.name}
            {openReasonIds.has(r.id) && <span className="reason-note">作業中</span>}
          </button>
        ))}
      </div>
    </section>
  );
});
