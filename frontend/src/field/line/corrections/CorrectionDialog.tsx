// 工程の記録を直す画面。記録を選び、開始・終了の時刻(大きなボタン)と生産数(テンキー)を変えるか、記録を取り消す。
// 理由は必須。送信が成功するまで閉じず、失敗の理由は画面の中に出す。
import { useState } from "react";
import { useI18n } from "../../../i18n/I18nProvider";
import type { RunEvent } from "../../../shared/api";
import { Dialog } from "../../../shared/Dialog";
import { Keypad } from "../dialogs/Keypad";
import { useSubmit } from "../dialogs/useSubmit";
import { recordLabel } from "../steps";
import { toJstIso } from "../timeScale";
import { ErrorLine, FixActions, RecordChoices } from "./parts";
import { type CorrectionReason, ReasonPicker, reasonReady } from "./ReasonPicker";
import { TimeStepper } from "./TimeStepper";

export type RunEventFields = { start_at?: string; end_at?: string; produced_qty?: number };

type Props = {
  title: string;
  records: RunEvent[]; // その工程の、取り消していない記録(開始の順)
  numbers: Map<number, number>;
  nowMs: number;
  /** 送る。成功したら null、失敗したら理由の文を返す。 */
  onFix: (e: RunEvent, fields: RunEventFields, reason: CorrectionReason, note: string) => Promise<string | null>;
  onVoid: (e: RunEvent, reason: CorrectionReason, note: string) => Promise<string | null>;
  onCancel: () => void;
};

export function CorrectionDialog({ records, ...rest }: Props) {
  const initial = records.find((e) => !e.end_at) ?? records[records.length - 1];
  const [id, setId] = useState(initial?.id ?? null);
  const record = records.find((e) => e.id === id) ?? null;
  // 記録を選び直したら、入力を最初からにする(key で作り直す)
  return <RecordForm key={id ?? "none"} record={record} records={records} onPick={setId} {...rest} />;
}

type FormProps = Omit<Props, "records"> & { record: RunEvent | null; records: RunEvent[]; onPick: (id: number) => void };

/** 時刻と生産数の入力。変えた項目だけを fields() で返す。 */
function useRecordInputs(record: RunEvent | null) {
  const originalStart = record ? Date.parse(record.start_at) : 0;
  const originalEnd = record?.end_at ? Date.parse(record.end_at) : null;
  const [startMs, setStartMs] = useState(originalStart);
  const [endMs, setEndMs] = useState(originalEnd);
  const [qty, setQty] = useState(record?.produced_qty == null ? "" : String(record.produced_qty));
  const hasQty = record?.step_type === "production" && originalEnd !== null;
  const fields = (): RunEventFields => {
    const f: RunEventFields = {};
    if (startMs !== originalStart) f.start_at = toJstIso(startMs);
    if (endMs !== null && endMs !== originalEnd) f.end_at = toJstIso(endMs);
    if (hasQty && qty !== "" && Number(qty) !== record?.produced_qty) f.produced_qty = Number(qty);
    return f;
  };
  return { originalStart, originalEnd, startMs, setStartMs, endMs, setEndMs, qty, setQty, hasQty, fields };
}

function RecordForm({ title, record, records, numbers, nowMs, onFix, onVoid, onCancel, onPick }: FormProps) {
  const { t } = useI18n();
  const inputs = useRecordInputs(record);
  const [reason, setReason] = useState<CorrectionReason | null>(null);
  const [note, setNote] = useState("");
  const [voiding, setVoiding] = useState(false);
  const { sending, error, submit } = useSubmit();

  const send = () => submit(async () => {
    if (!record) return t("correction.noRecords");
    if (!reasonReady(reason, note)) return t("correction.pickReason");
    if (voiding) return onVoid(record, reason, note.trim());
    const f = inputs.fields();
    return Object.keys(f).length === 0 ? t("correction.noChange") : onFix(record, f, reason, note.trim());
  });

  return (
    <Dialog title={title} wide onCancel={onCancel} actions={
      <FixActions voiding={voiding} setVoiding={setVoiding} sending={sending} hasTarget={record !== null}
        ready={reasonReady(reason, note)} onSend={send} />
    }>
      {records.length > 1 && (
        <>
          <p>{t("correction.pickRecord")}</p>
          <RecordChoices items={records.map((e) => ({ ...e, label: recordLabel(e, numbers, t) }))} selectedId={record?.id ?? null}
            disabled={sending} onPick={onPick} />
        </>
      )}
      {!record && <p>{t("correction.noRecords")}</p>}
      {record && voiding && <p className="confirm-message">{t("correction.voidMessage")}</p>}
      {record && !voiding && <RecordInputs record={record} inputs={inputs} nowMs={nowMs} disabled={sending} />}
      {record && <ReasonPicker reason={reason} note={note} onReason={setReason} onNote={setNote} disabled={sending} />}
      <ErrorLine error={error} />
    </Dialog>
  );
}

type InputsProps = { record: RunEvent; inputs: ReturnType<typeof useRecordInputs>; nowMs: number; disabled: boolean };

function RecordInputs({ record, inputs, nowMs, disabled }: InputsProps) {
  const { t } = useI18n();
  const { originalStart, originalEnd, startMs, setStartMs, endMs, setEndMs, qty, setQty, hasQty } = inputs;
  return (
    <div className={`fix-layout${hasQty ? "" : " fix-layout-single"}`}>
      <div className="fix-times">
        <TimeStepper label={t("correction.start")} valueMs={startMs} originalMs={originalStart} maxMs={nowMs}
          onChange={setStartMs} disabled={disabled} />
        {endMs !== null ? (
          <TimeStepper label={t("correction.end")} valueMs={endMs} originalMs={originalEnd} maxMs={nowMs}
            onChange={setEndMs} disabled={disabled} />
        ) : (
          <p className="fix-note">{t("correction.notEnded")}</p>
        )}
        {record.step_type === "production" && originalEnd === null && <p className="fix-note">{t("correction.qtyNotEnded")}</p>}
      </div>
      {hasQty && (
        <div className="fix-qty ng-pad">
          <p className="fix-section-title">{t("correction.qty")}</p>
          <Keypad text={qty} onChange={setQty} disabled={disabled} />
        </div>
      )}
    </div>
  );
}
