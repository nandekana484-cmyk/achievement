// 押し忘れた工程を後から記録する画面。工程を選び、開始と終了の時刻(大きなボタン)と、生産なら生産数(テンキー)を入れる。
import { useState } from "react";
import { useI18n } from "../../../i18n/I18nProvider";
import type { StepType } from "../../../shared/api";
import { Dialog } from "../../../shared/Dialog";
import { Keypad } from "../dialogs/Keypad";
import { useSubmit } from "../dialogs/useSubmit";
import { STEP_LABEL_KEYS, STEP_ORDER } from "../steps";
import { toJstIso } from "../timeScale";
import { ErrorLine } from "./parts";
import { type CorrectionReason, ReasonPicker, reasonReady } from "./ReasonPicker";
import { TimeStepper } from "./TimeStepper";

export type AddRecordInput = { step: StepType; startAt: string; endAt: string; producedQty: number | null };

type Props = {
  title: string;
  nowMs: number;
  onSubmit: (input: AddRecordInput, reason: CorrectionReason, note: string) => Promise<string | null>;
  onCancel: () => void;
};

const MINUTE = 60_000;

export function AddRecordDialog({ title, nowMs, onSubmit, onCancel }: Props) {
  const { t } = useI18n();
  // 最初は「30分前〜今」(分の単位にそろえる)
  const [endMs, setEndMs] = useState(() => Math.floor(nowMs / MINUTE) * MINUTE);
  const [startMs, setStartMs] = useState(() => Math.floor(nowMs / MINUTE) * MINUTE - 30 * MINUTE);
  const [step, setStep] = useState<StepType | null>(null);
  const [qty, setQty] = useState("");
  const [reason, setReason] = useState<CorrectionReason | null>("forgot");
  const [note, setNote] = useState("");
  const { sending, error, submit } = useSubmit();
  const needsQty = step === "production";
  const ready = step !== null && (!needsQty || qty !== "") && reasonReady(reason, note);

  const send = () => submit(async () => {
    if (step === null) return t("addRecord.pickStepFirst");
    if (!reasonReady(reason, note)) return t("correction.pickReason");
    const input = { step, startAt: toJstIso(startMs), endAt: toJstIso(endMs), producedQty: needsQty ? Number(qty) : null };
    return onSubmit(input, reason, note.trim());
  });

  return (
    <Dialog
      title={title}
      wide
      onCancel={onCancel}
      actions={
        <button type="button" className="btn btn-primary" disabled={sending || !ready} onClick={send}>
          {sending ? t("common.sending") : t("addRecord.submit")}
        </button>
      }
    >
      <p className="fix-section-title">{t("addRecord.pickStep")}</p>
      <div className="fix-steps" role="group" aria-label={t("addRecord.pickStep")}>
        {STEP_ORDER.map((s) => (
          <button key={s} type="button" className={`btn choice${s === step ? " choice-selected" : ""}`} aria-pressed={s === step}
            disabled={sending} onClick={() => setStep(s)}>
            {t(STEP_LABEL_KEYS[s])}
          </button>
        ))}
      </div>
      <div className={`fix-layout${needsQty ? "" : " fix-layout-single"}`}>
        <div className="fix-times">
          <p className="fix-section-title">{t("addRecord.times")}</p>
          <TimeStepper label={t("correction.start")} valueMs={startMs} maxMs={nowMs} onChange={setStartMs} disabled={sending} />
          <TimeStepper label={t("correction.end")} valueMs={endMs} maxMs={nowMs} onChange={setEndMs} disabled={sending} />
        </div>
        {needsQty && (
          <div className="fix-qty ng-pad">
            <p className="fix-section-title">{t("addRecord.qty")}</p>
            <Keypad text={qty} onChange={setQty} disabled={sending} />
          </div>
        )}
      </div>
      <ReasonPicker reason={reason} note={note} onReason={setReason} onNote={setNote} disabled={sending} />
      <ErrorLine error={error} />
    </Dialog>
  );
}
