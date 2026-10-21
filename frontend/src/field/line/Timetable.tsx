// 中央のタイムテーブル。縦軸が時刻(その日の 0:00〜24:00)、列は計画の枠・実績・付帯作業。
import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import type { Board, BoardPlan } from "../../shared/api";
import { STEP_COLORS, STEP_LABELS } from "./steps";
import { assignLanes, minutesInDay, minutesToY, type Span, spanFor, todayJst } from "./timeScale";

export const PX_PER_HOUR = 90;
const MIN_HEIGHT = 30; // 短い記録でも工程名が1行は読めるように
const TOUCH_MIN = 56; // 押す部分(計画の枠)の最低の高さ
const HOURS = Array.from({ length: 25 }, (_, h) => h);

export type TimetableHandle = { scrollToNow: () => void };

type Props = { board: Board; nowMs: number; selectedKey: string | null; onSelect: (key: string) => void };

export const planKey = (p: BoardPlan) => `${p.plan.kitting_no}|${p.plan.lot_no}`;

type Block = { key: string; span: Span; label: string; sub: string; color?: string; className: string; onClick?: () => void };

export const Timetable = forwardRef<TimetableHandle, Props>(function Timetable({ board, nowMs, selectedKey, onSelect }, ref) {
  const scroller = useRef<HTMLDivElement>(null);
  const isToday = board.date === todayJst(nowMs);
  const nowY = minutesToY(minutesInDay(nowMs, board.date), PX_PER_HOUR);

  const scrollToNow = () => {
    const el = scroller.current;
    if (el) el.scrollTop = Math.max(0, (isToday ? nowY : minutesToY(8 * 60, PX_PER_HOUR)) - el.clientHeight / 3);
  };
  useImperativeHandle(ref, () => ({ scrollToNow }));
  useEffect(scrollToNow, []); // 開いたときだけ

  const span = (start: string, end: string | null | undefined, minHeight = MIN_HEIGHT) =>
    spanFor(start, end, board.date, nowMs, PX_PER_HOUR, minHeight);

  const planBlocks: Block[] = board.plans.flatMap((p) => {
    const s = span(p.plan.planned_start, p.plan.planned_end, TOUCH_MIN);
    if (!s) return [];
    const selected = planKey(p) === selectedKey;
    const state = p.completed ? "完了" : selected ? "選択中" : `${Math.round((p.progress ?? 0) * 100)}%`;
    return [{
      key: planKey(p), span: s, label: p.plan.product_name, sub: `${p.plan.kitting_no}・${p.plan.run_no}回目・${state}`,
      className: `tt-plan${selected ? " tt-selected" : ""}${p.completed ? " tt-done" : ""}`, onClick: () => onSelect(planKey(p)),
    }];
  });

  const eventBlocks: Block[] = board.plans.flatMap((p) => p.events.flatMap((e) => {
    const s = span(e.start_at, e.end_at);
    if (!s) return [];
    const name = e.step_type === "production" ? `生産 ${e.seq}` : STEP_LABELS[e.step_type as keyof typeof STEP_LABELS];
    return [{
      key: `e${e.id}`, span: s, label: name, sub: `${p.plan.kitting_no}${e.end_at ? "" : "・作業中"}`,
      color: STEP_COLORS[e.step_type as keyof typeof STEP_COLORS], className: `tt-event${e.end_at ? "" : " tt-open"}`,
    }];
  }));

  const lineEventBlocks: Block[] = board.line_events.flatMap((e) => {
    const s = span(e.start_at, e.end_at);
    if (!s) return [];
    return [{ key: `l${e.id}`, span: s, label: e.reason_name, sub: e.end_at ? "" : "作業中", className: `tt-line-event${e.end_at ? "" : " tt-open"}` }];
  });

  return (
    <div className="timetable" ref={scroller}>
      <div className="tt-head">
        <span className="tt-hour-head">時刻</span>
        <span>計画</span>
        <span>実績</span>
        <span>付帯作業</span>
      </div>
      <div className="tt-body" style={{ height: 24 * PX_PER_HOUR }}>
        <div className="tt-hours">
          {HOURS.map((h) => (
            <span key={h} className="tt-hour" style={{ top: h * PX_PER_HOUR }}>{`${h}:00`}</span>
          ))}
        </div>
        <Column blocks={planBlocks} />
        <Column blocks={eventBlocks} />
        <Column blocks={lineEventBlocks} />
        {isToday && <div className="tt-now" style={{ top: nowY }} aria-label="今の時刻"><span>今</span></div>}
      </div>
    </div>
  );
});

function Column({ blocks }: { blocks: Block[] }) {
  const { lanes, laneCount } = assignLanes(blocks.map((b) => b.span));
  return (
    <div className="tt-col">
      {HOURS.slice(1).map((h) => <div key={h} className="tt-grid" style={{ top: h * PX_PER_HOUR }} />)}
      {blocks.map((b, i) => {
        const style = {
          top: b.span.top, height: b.span.height,
          left: `${(lanes[i] / laneCount) * 100}%`, width: `${100 / laneCount}%`,
          ...(b.color ? { borderLeftColor: b.color, background: `${b.color}22` } : {}),
        };
        const content = (<><span className="tt-label">{b.label}</span>{b.sub && <span className="tt-sub">{b.sub}</span>}</>);
        return b.onClick ? (
          <button key={b.key} type="button" className={`tt-block ${b.className}`} style={style} onClick={b.onClick}>{content}</button>
        ) : (
          <div key={b.key} className={`tt-block ${b.className}`} style={style}>{content}</div>
        );
      })}
    </div>
  );
}
