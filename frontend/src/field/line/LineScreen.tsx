// ライン画面(開発指針 7.1): 上部、左のメニュー、中央のタイムテーブル、右のパネル。
import { useRef, useState } from "react";
import { useParams } from "react-router-dom";
import type { Reason } from "../../shared/api";
import { Notice } from "../../shared/Notice";
import { useMasters } from "../../shared/useMasters";
import { useOperation } from "../../shared/useOperation";
import { LineDialogs, type DialogState } from "./LineDialogs";
import { LineEventPanel } from "./LineEventPanel";
import { SideMenu } from "./SideMenu";
import { StepPanel } from "./StepPanel";
import type { StepStatus } from "./steps";
import { planKey, Timetable, type TimetableHandle } from "./Timetable";
import { TopBar } from "./TopBar";
import { useBoard } from "./useBoard";
import { useLineActions } from "./useLineActions";
import { useNow } from "./useNow";

export function LineScreen() {
  const { lineCode = "" } = useParams();
  const { board, error: boardError, reload } = useBoard(lineCode);
  const { masters, error: mastersError } = useMasters(lineCode);
  const op = useOperation(reload);
  const actions = useLineActions(lineCode, op);
  const nowMs = useNow(10_000);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [dialog, setDialog] = useState<DialogState | null>(null);
  const timetable = useRef<TimetableHandle>(null);
  const lineEvents = useRef<HTMLElement>(null);

  const selected = board?.plans.find((p) => planKey(p) === selectedKey) ?? null;
  const lineName = masters?.lines.find((l) => l.line_code === board?.line_code)?.name ?? `${lineCode}ライン`;
  const openOperator = () => setDialog({ kind: "operator" });

  const onStep = (status: StepStatus) => {
    if (!selected) return;
    if (status.needsQty) setDialog({ kind: "qty", plan: selected, status });
    else if (status.needsReason) setDialog({ kind: "reason", plan: selected, status });
    else if (status.needsConfirm) setDialog({ kind: "confirm", plan: selected, status });
    else if (status.action === "start") void actions.startStep(selected, status.step);
    else void actions.endStep(selected, status.step);
  };
  const onLineEventStart = (reason: Reason) => {
    if (reason.requires_equipment || reason.requires_text) setDialog({ kind: "lineEvent", reason });
    else void actions.startLineEvent(reason.id, null, null);
  };

  return (
    <div className="line-screen">
      <TopBar lineName={lineName} board={board} onChangeOperator={openOperator} />
      <SideMenu
        onTimetable={() => timetable.current?.scrollToNow()}
        onLineEvents={() => lineEvents.current?.scrollIntoView({ behavior: "smooth" })}
        onChangeOperator={openOperator}
      />
      <section className="col-center">
        {board ? (
          <Timetable ref={timetable} board={board} nowMs={nowMs} selectedKey={selectedKey} onSelect={setSelectedKey} />
        ) : (
          <p className="placeholder">{boardError ?? "読み込み中…"}</p>
        )}
      </section>
      <aside className="col-right">
        {op.error && <Notice kind="error" onClose={op.clearError}>{op.error}</Notice>}
        {(boardError || mastersError) && board && <Notice kind="error">{boardError ?? mastersError}</Notice>}
        {board && !board.current_operator && (
          <Notice kind="info" action={<button type="button" className="btn btn-small" onClick={openOperator}>担当者を選ぶ</button>}>
            担当者が設定されていません。ボタンを押す前に、担当者を選んでください。
          </Notice>
        )}
        {selected ? (
          <StepPanel
            plan={selected}
            isBusy={op.isBusy}
            onStep={onStep}
            onNg={() => setDialog({ kind: "ng", plan: selected })}
            onRemark={() => setDialog({ kind: "remark", plan: selected })}
          />
        ) : (
          <p className="placeholder select-hint">タイムテーブルの計画を押すと、ここに工程のボタンが表示されます。</p>
        )}
        {board && masters && (
          <LineEventPanel
            ref={lineEvents}
            reasons={masters.reasons.filter((r) => r.usable_as_line_event)}
            openEvents={board.line_events.filter((e) => !e.end_at)}
            nowMs={nowMs}
            isBusy={op.isBusy}
            onStart={onLineEventStart}
            onEnd={(e) => void actions.endLineEvent(e)}
          />
        )}
      </aside>
      {dialog && board && masters && (
        <LineDialogs dialog={dialog} board={board} masters={masters} actions={actions} close={() => setDialog(null)} />
      )}
    </div>
  );
}
