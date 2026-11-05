// 計画終了と、その取り消しの画面。理由(その他は文で入れる。必須)と作業者IDを入れて確定する。
// 作業者IDは、ラインの今の担当者を最初から入れておく(紐づけのページと同じ)。詳細: docs/design/run-records.md
import { useState } from "react";
import { useI18n } from "../../../i18n/I18nProvider";
import { Dialog } from "../../../shared/Dialog";
import { useSubmit } from "./useSubmit";

export const CLOSE_REASONS = ["delay_stop", "plan_change", "other"] as const;
export type CloseReason = (typeof CLOSE_REASONS)[number];

type Props = {
  mode: "close" | "cancel";
  kittingNo: string;
  initialWorkerId: string;
  onSubmit: (workerId: string, reason: CloseReason, note: string) => Promise<string | null>;
  onCancel: () => void;
};

export function PlanCloseDialog({ mode, kittingNo, initialWorkerId, onSubmit, onCancel }: Props) {
  const { t } = useI18n();
  const [workerId, setWorkerId] = useState(initialWorkerId);
  const [reason, setReason] = useState<CloseReason | null>(null);
  const [note, setNote] = useState("");
  const { sending, error, submit } = useSubmit();
  const closing = mode === "close";
  const ready = workerId.trim() !== "" && (!closing || (reason !== null && (reason !== "other" || note.trim() !== "")));
  return (
    <Dialog
      title={`${t(closing ? "planClose.title" : "planClose.cancelTitle")} ${kittingNo}`}
      onCancel={onCancel}
      actions={
        <button type="button" className="btn btn-primary" disabled={!ready || sending}
          onClick={() => void submit(() => onSubmit(workerId.trim(), reason ?? "other", note.trim()))}>
          {t(closing ? "planClose.submit" : "planClose.cancelSubmit")}
        </button>
      }
    >
      <p>{t(closing ? "planClose.hint" : "planClose.cancelHint")}</p>
      {closing && (
        <fieldset className="close-reasons">
          <legend>{t("planClose.reason")}</legend>
          {CLOSE_REASONS.map((r) => (
            <label key={r} className="choice-row">
              <input type="radio" name="close-reason" checked={reason === r} onChange={() => setReason(r)} />
              {t(`planClose.reason.${r}`)}
            </label>
          ))}
          {reason === "other" && (
            <label className="field-label">
              {t("planClose.note")}
              <textarea className="text-input" rows={3} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
            </label>
          )}
        </fieldset>
      )}
      <label className="field-label">
        {t("planClose.workerId")}
        <input className="text-input" value={workerId} onChange={(e) => setWorkerId(e.target.value)} autoComplete="off" />
      </label>
      {error && <p className="dialog-error" role="alert">{error}</p>}
    </Dialog>
  );
}
