// ライン画面(開発指針 7.1): 上部、左のメニュー(検索)、中央のタイムテーブル、右のパネル。
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useI18n } from "../../i18n/I18nProvider";
import type { BoardPlan, LineEvent, Plan, Reason } from "../../shared/api";
import { lineName as displayLineName } from "../../shared/lineName";
import { Notice } from "../../shared/Notice";
import { useMasters } from "../../shared/useMasters";
import { useOperation } from "../../shared/useOperation";
import { LineDialogs, type DialogState } from "./LineDialogs";
import { LineEventPanel } from "./LineEventPanel";
import { isOutsideDisplay, outsideMessage } from "./planMatch";
import { PlanSearch } from "./PlanSearch";
import { SideMenu } from "./SideMenu";
import { StepPanel } from "./StepPanel";
import type { StepStatus } from "./steps";
import { Timetable, type TimetableHandle } from "./Timetable";
import { TopBar } from "./TopBar";
import { useBoard } from "./useBoard";
import { useLineActions } from "./useLineActions";
import { useNow } from "./useNow";
import { useSelectedPlan } from "./useSelectedPlan";

export function LineScreen() {
  const { lineCode = "" } = useParams();
  const { t } = useI18n();
  const { board, error: boardError, offsetMs, reload } = useBoard(lineCode);
  const { masters, error: mastersError } = useMasters(lineCode);
  const op = useOperation(reload);
  const actions = useLineActions(lineCode, op);
  const nowMs = useNow(5_000, offsetMs);
  const [selectedKno, setSelectedKno] = useState<string | null>(null);
  const [dialog, setDialog] = useState<DialogState | null>(null);
  const timetable = useRef<TimetableHandle>(null);
  const lineEvents = useRef<HTMLElement>(null);
  const rightPanel = useRef<HTMLElement>(null);

  // 計画を選び直したら、右のパネルを先頭(選んだ計画の見出しとロットの一覧)に戻す
  useEffect(() => {
    if (rightPanel.current) rightPanel.current.scrollTop = 0;
  }, [selectedKno]);

  const selected = useSelectedPlan(board, selectedKno);
  const line = masters?.lines.find((l) => l.line_code === board?.line_code);
  const lineName = line ? displayLineName(line, t) : t("lineScreen.lineFallback", { code: lineCode });
  const openOperator = () => setDialog({ kind: "operator" });
  const select = (p: Plan) => setSelectedKno(p.kitting_no);

  // 記録のボタンは、担当者が未設定ならサーバーに送らず、先に担当者を選ぶ画面を出す
  const withOperator = (action: () => void) => () => {
    if (!board?.current_operator) setDialog({ kind: "operator", message: t("lineScreen.pickOperatorFirst") });
    else action();
  };
  const onStep = (plan: BoardPlan, status: StepStatus) => withOperator(() => {
    if (status.needsQty) setDialog({ kind: "qty", plan, status });
    else if (status.needsReason) setDialog({ kind: "reason", plan, status });
    else if (status.needsConfirm) setDialog({ kind: "confirm", plan, status });
    else if (status.action === "start") void actions.startStep(plan, status.step);
    else void actions.endStep(plan, status.step);
  })();
  const onLineEventStart = (reason: Reason) => withOperator(() => {
    if (reason.requires_equipment || reason.requires_text) setDialog({ kind: "lineEvent", reason });
    else void actions.startLineEvent(reason.id, null, null);
  })();
  const onLineEventEnd = (e: LineEvent) => withOperator(() => void actions.endLineEvent(e))();

  return (
    <div className="line-screen">
      <TopBar lineName={lineName} board={board} onChangeOperator={openOperator} />
      <SideMenu
        search={<PlanSearch lineCode={lineCode} onPick={select} />}
        onTimetable={() => timetable.current?.scrollToNow()}
        onLineEvents={() => lineEvents.current?.scrollIntoView({ behavior: "smooth" })}
        onChangeOperator={openOperator}
      />
      <section className="col-center">
        {board && selected && isOutsideDisplay(selected.plan, board) && (
          <Notice kind="info">{outsideMessage(selected.plan, t)}</Notice>
        )}
        {board ? (
          <Timetable ref={timetable} board={board} nowMs={nowMs} selectedKey={selectedKno} onSelect={(p) => select(p.plan)} />
        ) : (
          <p className="placeholder">{boardError ?? t("common.loading")}</p>
        )}
      </section>
      <aside className="col-right" ref={rightPanel}>
        {op.error && <Notice kind="error" onClose={op.clearError}>{op.error}</Notice>}
        {(boardError || mastersError) && board && <Notice kind="error">{boardError ?? mastersError}</Notice>}
        {board && !board.current_operator && (
          <Notice kind="info" action={<button type="button" className="btn btn-small" onClick={openOperator}>{t("lineScreen.pickOperator")}</button>}>
            {t("lineScreen.noOperator")}
          </Notice>
        )}
        {selected ? (
          <StepPanel
            plan={selected}
            isBusy={op.isBusy}
            onStep={(status) => onStep(selected, status)}
            onNg={withOperator(() => setDialog({ kind: "ng", plan: selected }))}
            onRemark={withOperator(() => setDialog({ kind: "remark", plan: selected }))}
          />
        ) : (
          <p className="placeholder select-hint">{t("lineScreen.selectHint")}</p>
        )}
        {board && masters && (
          <LineEventPanel
            ref={lineEvents}
            reasons={masters.reasons.filter((r) => r.usable_as_line_event)}
            openEvents={board.line_events.filter((e) => !e.end_at)}
            nowMs={nowMs}
            isBusy={op.isBusy}
            onStart={onLineEventStart}
            onEnd={onLineEventEnd}
          />
        )}
      </aside>
      {dialog && board && masters && (
        <LineDialogs dialog={dialog} board={board} masters={masters} actions={actions} close={() => setDialog(null)} />
      )}
    </div>
  );
}
