// ライン画面のダイアログの出し分け。どのダイアログを出すかは LineScreen が DialogState で決める。
import type { Board, BoardPlan, Masters, Reason } from "../../shared/api";
import { ConfirmDialog } from "./dialogs/ConfirmDialog";
import { LineEventStartDialog } from "./dialogs/LineEventStartDialog";
import { NumberPadDialog } from "./dialogs/NumberPadDialog";
import { RestartReasonDialog } from "./dialogs/RestartReasonDialog";
import { TextDialog } from "./dialogs/TextDialog";
import { OperatorPicker } from "./OperatorPicker";
import type { StepStatus } from "./steps";
import type { LineActions } from "./useLineActions";

export type DialogState =
  | { kind: "operator" }
  | { kind: "qty"; plan: BoardPlan; status: StepStatus }
  | { kind: "reason"; plan: BoardPlan; status: StepStatus }
  | { kind: "confirm"; plan: BoardPlan; status: StepStatus }
  | { kind: "ng"; plan: BoardPlan }
  | { kind: "remark"; plan: BoardPlan }
  | { kind: "lineEvent"; reason: Reason };

type Props = { dialog: DialogState; board: Board; masters: Masters; actions: LineActions; close: () => void };

export function LineDialogs({ dialog, board, masters, actions, close }: Props) {
  // ダイアログはすぐ閉じ、結果(成功・失敗)は画面のお知らせと board の読み直しで分かるようにする
  const then = (send: () => void) => () => {
    close();
    send();
  };
  switch (dialog.kind) {
    case "operator":
      return (
        <OperatorPicker
          operators={masters.operators}
          currentId={board.current_operator?.operator_id ?? null}
          onPick={(id) => then(() => actions.changeOperator(id))()}
          onCancel={close}
        />
      );
    case "qty":
      return (
        <NumberPadDialog
          title={`${dialog.status.label}の終了`}
          message="この区切りで生産した数を入れてください。"
          submitLabel="生産を終了"
          onSubmit={(n) => then(() => actions.endStep(dialog.plan, "production", n))()}
          onCancel={close}
        />
      );
    case "reason":
      return (
        <RestartReasonDialog
          title={`${dialog.status.label}の開始`}
          reasons={masters.reasons.filter((r) => r.usable_as_restart)}
          equipment={masters.equipment}
          onSubmit={(reasonId, equipmentId) => then(() => actions.startStep(dialog.plan, "production", reasonId, equipmentId))()}
          onCancel={close}
        />
      );
    case "confirm":
      return (
        <ConfirmDialog
          title="片付けの終了"
          message="片付けを終了すると、この計画は完了になります。"
          confirmLabel="片付けを終了"
          onConfirm={then(() => actions.endStep(dialog.plan, "cleanup"))}
          onCancel={close}
        />
      );
    case "ng":
      return (
        <NumberPadDialog
          title="NG数の入力"
          initial={dialog.plan.ng_qty}
          submitLabel="NG数を記録"
          onSubmit={(n) => then(() => actions.setNg(dialog.plan, n))()}
          onCancel={close}
        />
      );
    case "remark":
      return (
        <TextDialog title="備考の入力" label="備考" submitLabel="備考を記録" onSubmit={(t) => then(() => actions.addRemark(dialog.plan, t))()} onCancel={close} />
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
  }
}
