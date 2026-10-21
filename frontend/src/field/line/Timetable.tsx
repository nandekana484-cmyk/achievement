// 中央のタイムテーブル。縦軸は表示範囲の48時間(稼働日の前後12時間を含む)、列は計画の枠・実績・付帯作業。
import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import type { Board, BoardPlan } from "../../shared/api";
import { STEP_COLORS, STEP_LABELS } from "./steps";
import { assignLanes, formatHM, formatMD, hourTicks, minutesFrom, minutesToY, type Span, spanFor } from "./timeScale";

export const PX_PER_HOUR = 90;
const MIN_HEIGHT = 30; // 短い記録でも工程名が1行は読めるように
const TOUCH_MIN = 56; // 押す部分(計画の枠)の最低の高さ

export type TimetableHandle = { scrollToNow: () => void };

type Props = { board: Board; nowMs: number; selectedKey: string | null; onSelect: (plan: BoardPlan) => void };

export const planKey = (p: BoardPlan) => `${p.plan.kitting_no}|${p.plan.lot_no}`;

type Block = { key: string; span: Span; label: string; sub: string; color?: string; className: string; onClick?: () => void };

export const Timetable = forwardRef<TimetableHandle, Props>(function Timetable({ board, nowMs, selectedKey, onSelect }, ref) {
  const scroller = useRef<HTMLDivElement>(null);
  const origin = Date.parse(board.display_start);
  const total = minutesFrom(board.display_end, origin);
  const y = (time: string | number) => minutesToY(minutesFrom(time, origin), PX_PER_HOUR);
  const nowInRange = nowMs >= origin && nowMs <= Date.parse(board.display_end);

  const scrollToNow = () => {
    const el = scroller.current;
    if (el) el.scrollTop = Math.max(0, y(nowInRange ? nowMs : board.workday_start) - el.clientHeight / 3);
  };
  useImperativeHandle(ref, () => ({ scrollToNow }));
  useEffect(scrollToNow, []); // 開いたときだけ

  const span = (start: string | null | undefined, end: string | null | undefined, minHeight = MIN_HEIGHT) =>
    spanFor(start, end, origin, total, nowMs, PX_PER_HOUR, minHeight);

  const planBlocks: Block[] = board.plans.flatMap((p) => {
    const s = span(p.plan.planned_start, p.plan.planned_end, TOUCH_MIN);
    if (!s) return [];
    const selected = planKey(p) === selectedKey;
    const state = p.completed ? "完了" : selected ? "選択中" : `${Math.round((p.progress ?? 0) * 100)}%`;
    const clip = `${s.clippedStart ? " tt-clip-start" : ""}${s.clippedEnd ? " tt-clip-end" : ""}`;
    return [{
      key: planKey(p), span: s, label: p.plan.product_name, sub: `${p.plan.kitting_no}・${p.plan.run_no}回目・${state}`,
      className: `tt-plan${selected ? " tt-selected" : ""}${p.completed ? " tt-done" : ""}${clip}`, onClick: () => onSelect(p),
    }];
  });

  const eventBlocks: Block[] = board.plans.flatMap((p) => p.events.flatMap((e) => {
    const s = span(e.start_at, e.end_at);
    if (!s) return [];
    const step = e.step_type as keyof typeof STEP_LABELS;
    return [{
      key: `e${e.id}`, span: s, label: step === "production" ? `生産 ${e.seq}` : STEP_LABELS[step],
      sub: `${p.plan.kitting_no}${e.end_at ? "" : "・作業中"}`, color: STEP_COLORS[step], className: `tt-event${e.end_at ? "" : " tt-open"}`,
    }];
  }));

  const lineEventBlocks: Block[] = board.line_events.flatMap((e) => {
    const s = span(e.start_at, e.end_at);
    if (!s) return [];
    return [{ key: `l${e.id}`, span: s, label: e.reason_name, sub: e.end_at ? "" : "作業中", className: `tt-line-event${e.end_at ? "" : " tt-open"}` }];
  });

  const nextDay = new Date(Date.parse(board.workday_end) + 9 * 3600_000).toISOString().slice(0, 10);
  const dayStart = formatHM(board.workday_start).replace(/^0/, "");
  const ticks = hourTicks(origin, Date.parse(board.display_end));
  const gridTops = ticks.map((t) => y(t.ms));
  return (
    <div className="timetable" ref={scroller}>
      <div className="tt-head">
        <span className="tt-hour-head">時刻</span>
        <span>計画</span>
        <span>実績</span>
        <span>付帯作業</span>
      </div>
      <div className="tt-body" style={{ height: minutesToY(total, PX_PER_HOUR) }}>
        <div className="tt-hours">
          {ticks.map((t) => (
            <span key={t.ms} className="tt-hour" style={{ top: y(t.ms) }}>{t.label}</span>
          ))}
        </div>
        <Column blocks={planBlocks} ticks={gridTops} />
        <Column blocks={eventBlocks} ticks={gridTops} />
        <Column blocks={lineEventBlocks} ticks={gridTops} />
        <Boundary top={y(board.workday_start)} label={`${formatMD(board.date)} 稼働日の始まり(${dayStart})`} />
        <Boundary top={y(board.workday_end)} label={`${formatMD(nextDay)} 次の稼働日の始まり(${dayStart})`} />
        {nowInRange && <div className="tt-now" style={{ top: y(nowMs) }} aria-label="今の時刻"><span>今</span></div>}
      </div>
    </div>
  );
});

function Boundary({ top, label }: { top: number; label: string }) {
  return (
    <div className="tt-boundary" style={{ top }} aria-label={label}>
      <span>{label}</span>
    </div>
  );
}

function Column({ blocks, ticks }: { blocks: Block[]; ticks: number[] }) {
  const { lanes, laneCount } = assignLanes(blocks.map((b) => b.span));
  return (
    <div className="tt-col">
      {ticks.map((top) => <div key={top} className="tt-grid" style={{ top }} />)}
      {blocks.map((b, i) => {
        const style = {
          top: b.span.top, height: b.span.height,
          left: `${(lanes[i] / laneCount) * 100}%`, width: `${100 / laneCount}%`,
          ...(b.color ? { borderLeftColor: b.color, background: `${b.color}22` } : {}),
        };
        const content = (
          <>
            {b.span.clippedStart && <span className="tt-clip-mark">▲ 表示範囲の前から続く</span>}
            <span className="tt-label">{b.label}</span>
            {b.sub && <span className="tt-sub">{b.sub}</span>}
            {b.span.clippedEnd && <span className="tt-clip-mark tt-clip-mark-end">▼ 表示範囲の後へ続く</span>}
          </>
        );
        return b.onClick ? (
          <button key={b.key} type="button" className={`tt-block ${b.className}`} style={style} onClick={b.onClick}>{content}</button>
        ) : (
          <div key={b.key} className={`tt-block ${b.className}`} style={style}>{content}</div>
        );
      })}
    </div>
  );
}
