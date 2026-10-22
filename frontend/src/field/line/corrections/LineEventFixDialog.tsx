// 付帯作業を直す画面。付帯作業を選び、開始・終了の時刻、理由(設備・記入が必要な理由ならそれも)を変えるか、取り消す。
import { useState } from "react";
import { useI18n } from "../../../i18n/I18nProvider";
import { localName } from "../../../i18n/translate";
import type { Equipment, LineEvent, Reason } from "../../../shared/api";
import { Dialog } from "../../../shared/Dialog";
import { EquipmentChoices } from "../dialogs/RestartReasonDialog";
import { useSubmit } from "../dialogs/useSubmit";
import { toJstIso } from "../timeScale";
import { ErrorLine, FixActions, RecordChoices } from "./parts";
import { type CorrectionReason, ReasonPicker, reasonReady } from "./ReasonPicker";
import { TimeStepper } from "./TimeStepper";

export type LineEventFields = {
  start_at?: string; end_at?: string; reason_id?: number; equipment_id?: number | null; reason_text?: string | null;
};

type Props = {
  events: LineEvent[]; // 取り消していない付帯作業(新しい順)
  reasons: Reason[]; // 付帯作業として使える理由
  equipment: Equipment[];
  nowMs: number;
  onFix: (e: LineEvent, fields: LineEventFields, reason: CorrectionReason, note: string) => Promise<string | null>;
  onVoid: (e: LineEvent, reason: CorrectionReason, note: string) => Promise<string | null>;
  onCancel: () => void;
};

export function LineEventFixDialog({ events, ...rest }: Props) {
  const [id, setId] = useState(events[0]?.id ?? null);
  const event = events.find((e) => e.id === id) ?? null;
  return <EventForm key={id ?? "none"} event={event} events={events} onPick={setId} {...rest} />;
}

/** 時刻・理由・設備・記入の入力。変えた項目だけを fields() で返す。 */
function useEventInputs(event: LineEvent | null) {
  const originalStart = event ? Date.parse(event.start_at) : 0;
  const originalEnd = event?.end_at ? Date.parse(event.end_at) : null;
  const [startMs, setStartMs] = useState(originalStart);
  const [endMs, setEndMs] = useState(originalEnd);
  const [reasonId, setReasonId] = useState(event?.reason_id ?? null);
  const [equipmentId, setEquipmentId] = useState(event?.equipment_id ?? null);
  const [text, setText] = useState(event?.reason_text ?? "");
  // 設備や記入が要らない理由に変えたら、設備と記入は消す(付帯作業の開始のときと同じ形にする)
  const pickReason = (r: Reason) => {
    setReasonId(r.id);
    if (!r.requires_equipment) setEquipmentId(null);
    if (!r.requires_text) setText("");
  };
  const fields = (): LineEventFields => {
    const f: LineEventFields = {};
    if (!event) return f;
    if (startMs !== originalStart) f.start_at = toJstIso(startMs);
    if (endMs !== null && endMs !== originalEnd) f.end_at = toJstIso(endMs);
    if (reasonId !== null && reasonId !== event.reason_id) f.reason_id = reasonId;
    if (equipmentId !== (event.equipment_id ?? null)) f.equipment_id = equipmentId;
    if ((text.trim() || null) !== (event.reason_text ?? null)) f.reason_text = text.trim() || null;
    return f;
  };
  return { originalStart, originalEnd, startMs, setStartMs, endMs, setEndMs, reasonId, pickReason, equipmentId, setEquipmentId,
    text, setText, fields };
}

type FormProps = Omit<Props, "events"> & { event: LineEvent | null; events: LineEvent[]; onPick: (id: number) => void };

function EventForm({ event, events, reasons, equipment, nowMs, onFix, onVoid, onCancel, onPick }: FormProps) {
  const { t, lang } = useI18n();
  const inputs = useEventInputs(event);
  const [reason, setReason] = useState<CorrectionReason | null>(null);
  const [note, setNote] = useState("");
  const [voiding, setVoiding] = useState(false);
  const { sending, error, submit } = useSubmit();

  const send = () => submit(async () => {
    if (!event) return t("lineEventFix.none");
    if (!reasonReady(reason, note)) return t("correction.pickReason");
    if (voiding) return onVoid(event, reason, note.trim());
    const f = inputs.fields();
    return Object.keys(f).length === 0 ? t("correction.noChange") : onFix(event, f, reason, note.trim());
  });

  return (
    <Dialog title={t("lineEventFix.title")} wide onCancel={onCancel} actions={
      <FixActions voiding={voiding} setVoiding={setVoiding} sending={sending} hasTarget={event !== null}
        ready={reasonReady(reason, note)} onSend={send} />
    }>
      {events.length === 0 ? <p>{t("lineEventFix.none")}</p> : (
        <>
          <p>{t("lineEventFix.pick")}</p>
          <RecordChoices items={events.map((e) => ({ ...e, label: localName(lang, e.reason_name, e.reason_name_vi) }))}
            selectedId={event?.id ?? null} disabled={sending} onPick={onPick} />
        </>
      )}
      {event && voiding && <p className="confirm-message">{t("correction.voidMessage")}</p>}
      {event && !voiding && <EventInputs inputs={inputs} reasons={reasons} equipment={equipment} nowMs={nowMs} disabled={sending} />}
      {event && <ReasonPicker reason={reason} note={note} onReason={setReason} onNote={setNote} disabled={sending} />}
      <ErrorLine error={error} />
    </Dialog>
  );
}

type InputsProps = {
  inputs: ReturnType<typeof useEventInputs>; reasons: Reason[]; equipment: Equipment[]; nowMs: number; disabled: boolean;
};

function EventInputs({ inputs, reasons, equipment, nowMs, disabled }: InputsProps) {
  const { t, lang } = useI18n();
  const { originalStart, originalEnd, startMs, setStartMs, endMs, setEndMs, reasonId, pickReason } = inputs;
  const lineReason = reasons.find((r) => r.id === reasonId);
  return (
    <>
      <div className="fix-layout">
        <TimeStepper label={t("correction.start")} valueMs={startMs} originalMs={originalStart} maxMs={nowMs}
          onChange={setStartMs} disabled={disabled} />
        {endMs !== null ? (
          <TimeStepper label={t("correction.end")} valueMs={endMs} originalMs={originalEnd} maxMs={nowMs}
            onChange={setEndMs} disabled={disabled} />
        ) : <p className="fix-note">{t("correction.notEnded")}</p>}
      </div>
      <p className="fix-section-title">{t("lineEventFix.reasonTitle")}</p>
      <div className="choice-grid">
        {reasons.map((r) => (
          <button key={r.id} type="button" className={`btn choice${r.id === reasonId ? " choice-selected" : ""}`}
            aria-pressed={r.id === reasonId} disabled={disabled} onClick={() => pickReason(r)}>
            {localName(lang, r.name, r.name_vi)}
          </button>
        ))}
      </div>
      {lineReason?.requires_equipment && (
        <>
          <p className="fix-section-title">{t("lineEventFix.equipment")}</p>
          <EquipmentChoices equipment={equipment} selected={inputs.equipmentId} onSelect={inputs.setEquipmentId} />
        </>
      )}
      {lineReason?.requires_text && (
        <label className="field-label">
          {t("lineEventFix.text")}
          <textarea className="text-input" rows={2} maxLength={2000} value={inputs.text} disabled={disabled}
            onChange={(e) => inputs.setText(e.target.value)} />
        </label>
      )}
    </>
  );
}
