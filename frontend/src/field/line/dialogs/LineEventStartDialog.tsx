// 付帯作業の開始で、設備や理由の記入が必要なときに出す画面。
import { useState } from "react";
import type { Equipment, Reason } from "../../../shared/api";
import { Dialog } from "../../../shared/Dialog";
import { EquipmentChoices } from "./RestartReasonDialog";

type Props = {
  reason: Reason;
  equipment: Equipment[];
  onSubmit: (equipmentId: number | null, text: string | null) => void;
  onCancel: () => void;
};

export function LineEventStartDialog({ reason, equipment, onSubmit, onCancel }: Props) {
  const [equipmentId, setEquipmentId] = useState<number | null>(null);
  const [text, setText] = useState("");
  const ready = (!reason.requires_equipment || equipmentId !== null) && (!reason.requires_text || text.trim() !== "");

  return (
    <Dialog
      title={`${reason.name}を開始`}
      onCancel={onCancel}
      actions={
        <button type="button" className="btn btn-primary" disabled={!ready} onClick={() => onSubmit(equipmentId, text.trim() || null)}>
          開始
        </button>
      }
    >
      {reason.requires_equipment && (
        <>
          <p>設備を選んでください(必須)。</p>
          <EquipmentChoices equipment={equipment} selected={equipmentId} onSelect={setEquipmentId} />
        </>
      )}
      {reason.requires_text && (
        <label className="field-label">
          理由(必須)
          <textarea className="text-input" rows={3} maxLength={2000} value={text} onChange={(e) => setText(e.target.value)} />
        </label>
      )}
    </Dialog>
  );
}
