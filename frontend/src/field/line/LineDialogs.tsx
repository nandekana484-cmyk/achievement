// ライン画面のダイアログの出し分け。どのダイアログを出すかは LineScreen が DialogState で決める。
import { useI18n } from "../../i18n/I18nProvider";
import type { Board, BoardPlan, Masters, Reason } from "../../shared/api";
import type { RunResult } from "../../shared/useOperation";
import { type CorrectionDialogState, CorrectionDialogs } from "./CorrectionDialogs";
import { ConfirmDialog } from "./dialogs/ConfirmDialog";
import { LineEventStartDialog } from "./dialogs/LineEventStartDialog";
import { NgDialog } from "./dialogs/NgDialog";
import { NumberPadDialog } from "./dialogs/NumberPadDialog";
import { RestartReasonDialog } from "./dialogs/RestartReasonDialog";
import { TextDialog } from "./dialogs/TextDialog";
import { OperatorPicker } from "./OperatorPicker";
import type { StepStatus } from "./steps";
import type { LineActions } from "./useLineActions";

export type DialogState =
  | { kind: "operator"; message?: string }
  | { kind: "qty"; plan: BoardPlan; status: StepStatus }
  | { kind: "reason"; plan: BoardPlan; status: StepStatus }
  | { kind: "confirm"; plan: BoardPlan; status: StepStatus }
  | { kind: "ng"; plan: BoardPlan }
  | { kind: "remark"; plan: BoardPlan }
  | { kind: "lineEvent"; reason: Reason }
  | CorrectionDialogState;

type Props = { dialog: DialogState; board: Board; masters: Masters; actions: LineActions; nowMs: number; close: () => void };

export function LineDialogs({ dialog, board, masters, actions, nowMs, close }: Props) {
  const { t } = useI18n();
  // 選ぶだけのダイアログはすぐ閉じ、結果は画面のお知らせと board の読み直しで分かるようにする
  const then = (send: () => void) => () => {
    close();
    send();
  };
  // テンキーは送信が成功するまで閉じない(失敗の理由はダイアログの中に出す)
  const untilSuccess = async (send: Promise<RunResult<unknown>>): Promise<string | null> => {
    const r = await send;
    if (r.ok) close();
    return r.ok ? null : r.message;
  };
  switch (dialog.kind) {
    case "operator":
      return (
        <OperatorPicker
          message={dialog.message}
          operators={masters.operators}
          currentId={board.current_operator?.operator_id ?? null}
          onPick={(id) => then(() => actions.changeOperator(id))()}
          onCancel={close}
        />
      );
    case "qty":
      return (
        <NumberPadDialog
          title={t("productionEnd.title", { step: dialog.status.label })}
          message={t("productionEnd.message")}
          submitLabel={t("productionEnd.submit")}
          onSubmit={(n) => untilSuccess(actions.endStep(dialog.plan, "production", n, { showError: false }))}
          onCancel={close}
        />
      );
    case "reason":
      return (
        <RestartReasonDialog
          title={t("restart.title", { step: dialog.status.label })}
          reasons={masters.reasons.filter((r) => r.usable_as_restart)}
          equipment={masters.equipment}
          onSubmit={(reasonId, equipmentId) => then(() => actions.startStep(dialog.plan, "production", reasonId, equipmentId))()}
          onCancel={close}
        />
      );
    case "confirm":
      return (
        <ConfirmDialog
          title={t("cleanup.title")}
          message={t("cleanup.message")}
          confirmLabel={t("cleanup.confirm")}
          onConfirm={then(() => actions.endStep(dialog.plan, "cleanup"))}
          onCancel={close}
        />
      );
    case "ng":
      return (
        <NgDialog
          plan={dialog.plan}
          onSubmit={(lot, side, n) => untilSuccess(actions.setNg(dialog.plan, lot, side, n, { showError: false }))}
          onCancel={close}
        />
      );
    case "remark":
      return (
        <TextDialog title={t("remark.title")} label={t("remark.label")} submitLabel={t("remark.submit")}
          onSubmit={(text) => then(() => actions.addRemark(dialog.plan, text))()} onCancel={close} />
      );
    case "lineEvent":
      return (
        <LineEventStartDialog
          reason={dialog.reason}
          equipment={masters.equipment}
          onSubmit={(eq, text) => then(() => actions.startLineEvent(dialog.reason.id, eq, text))()}
          onCancel={close}
        />
      );
    default:
      return <CorrectionDialogs dialog={dialog} board={board} masters={masters} actions={actions} nowMs={nowMs} close={close} />;
  }
}
