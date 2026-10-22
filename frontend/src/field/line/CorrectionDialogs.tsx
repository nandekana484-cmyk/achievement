// ライン画面の訂正のダイアログの出し分け(工程の記録を直す・押し忘れの追加・訂正の履歴・付帯作業を直す・その履歴)。
import { useI18n } from "../../i18n/I18nProvider";
import type { Board, BoardPlan, Masters, StepType } from "../../shared/api";
import type { RunResult } from "../../shared/useOperation";
import { AddRecordDialog } from "./corrections/AddRecordDialog";
import { CorrectionDialog } from "./corrections/CorrectionDialog";
import { HistoryDialog } from "./corrections/HistoryDialog";
import { LineEventFixDialog } from "./corrections/LineEventFixDialog";
import { LineEventHistoryDialog } from "./corrections/LineEventHistoryDialog";
import { recordNumbers, STEP_LABEL_KEYS, stepStatus } from "./steps";
import type { LineActions } from "./useLineActions";

export type CorrectionDialogState =
  | { kind: "fix"; plan: BoardPlan; step: StepType }
  | { kind: "add"; plan: BoardPlan }
  | { kind: "history"; plan: BoardPlan }
  | { kind: "lineFix" }
  | { kind: "lineHistory" };

type Props = {
  dialog: CorrectionDialogState; board: Board; masters: Masters; actions: LineActions; nowMs: number; close: () => void;
};

const newestFirst = <T extends { start_at: string }>(items: T[]) =>
  [...items].sort((a, b) => Date.parse(b.start_at) - Date.parse(a.start_at));

export function CorrectionDialogs({ dialog, board, masters, actions, nowMs, close }: Props) {
  const { t } = useI18n();
  // 送信が成功するまで閉じない(失敗の理由はダイアログの中に出す)
  const untilSuccess = async (send: Promise<RunResult<unknown>>): Promise<string | null> => {
    const r = await send;
    if (r.ok) close();
    return r.ok ? null : r.message;
  };
  switch (dialog.kind) {
    case "fix": {
      const { plan, step } = dialog;
      return (
        <CorrectionDialog
          title={t("correction.title", { step: t(STEP_LABEL_KEYS[step]) })}
          records={stepStatus(plan.events, step, t).records}
          numbers={recordNumbers(plan.events)}
          nowMs={nowMs}
          onFix={(e, fields, reason, note) => untilSuccess(actions.fixRunEvent(plan, e, fields, reason, note))}
          onVoid={(e, reason, note) => untilSuccess(actions.voidRunEvent(plan, e, reason, note))}
          onCancel={close}
        />
      );
    }
    case "add":
      return (
        <AddRecordDialog
          title={t("addRecord.title")}
          nowMs={nowMs}
          onSubmit={(input, reason, note) => untilSuccess(actions.addRunEvent(dialog.plan, input, reason, note))}
          onCancel={close}
        />
      );
    case "history":
      return <HistoryDialog plan={dialog.plan} onClose={close} />;
    case "lineFix":
      return (
        <LineEventFixDialog
          events={newestFirst(board.line_events.filter((e) => !e.voided_at))}
          reasons={masters.reasons.filter((r) => r.usable_as_line_event)}
          equipment={masters.equipment}
          nowMs={nowMs}
          onFix={(e, fields, reason, note) => untilSuccess(actions.fixLineEvent(e, fields, reason, note))}
          onVoid={(e, reason, note) => untilSuccess(actions.voidLineEvent(e, reason, note))}
          onCancel={close}
        />
      );
    case "lineHistory":
      return <LineEventHistoryDialog lineCode={board.line_code} date={board.date} events={newestFirst(board.line_events)} onClose={close} />;
  }
}
