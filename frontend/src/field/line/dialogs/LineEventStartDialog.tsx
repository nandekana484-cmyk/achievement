// 付帯作業の開始で、設備や理由の記入が必要なときに出す画面。
import { useState } from "react";
import { useI18n } from "../../../i18n/I18nProvider";
import { localName } from "../../../i18n/translate";
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
  const { t, lang } = useI18n();
  const [equipmentId, setEquipmentId] = useState<number | null>(null);
  const [text, setText] = useState("");
  const ready = (!reason.requires_equipment || equipmentId !== null) && (!reason.requires_text || text.trim() !== "");

  return (
    <Dialog
      title={t("lineEvent.startTitle", { reason: localName(lang, reason.name, reason.name_vi) })}
      onCancel={onCancel}
      actions={
        <button type="button" className="btn btn-primary" disabled={!ready} onClick={() => onSubmit(equipmentId, text.trim() || null)}>
          {t("common.start")}
        </button>
      }
    >
      {reason.requires_equipment && (
        <>
          <p>{t("lineEvent.pickEquipment")}</p>
          <EquipmentChoices equipment={equipment} selected={equipmentId} onSelect={setEquipmentId} />
        </>
      )}
      {reason.requires_text && (
        <label className="field-label">
          {t("lineEvent.reasonText")}
          <textarea className="text-input" rows={3} maxLength={2000} value={text} onChange={(e) => setText(e.target.value)} />
        </label>
      )}
    </Dialog>
  );
}
