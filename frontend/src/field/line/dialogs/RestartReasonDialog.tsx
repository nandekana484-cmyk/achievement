// 生産の2回目以降の開始で、再開理由を選ぶ画面。設備が必要な理由なら、設備も選べる(任意)。
import { useState } from "react";
import { useI18n } from "../../../i18n/I18nProvider";
import { localName } from "../../../i18n/translate";
import type { Equipment, Reason } from "../../../shared/api";
import { Dialog } from "../../../shared/Dialog";

type Props = {
  title: string;
  reasons: Reason[];
  equipment: Equipment[];
  onSubmit: (reasonId: number, equipmentId: number | null) => void;
  onCancel: () => void;
};

export function RestartReasonDialog({ title, reasons, equipment, onSubmit, onCancel }: Props) {
  const { t, lang } = useI18n();
  const [reasonId, setReasonId] = useState<number | null>(null);
  const [equipmentId, setEquipmentId] = useState<number | null>(null);
  const reason = reasons.find((r) => r.id === reasonId);

  const pickReason = (id: number) => {
    setReasonId(id);
    setEquipmentId(null);
  };

  return (
    <Dialog
      title={title}
      wide
      onCancel={onCancel}
      actions={
        <button type="button" className="btn btn-primary" disabled={reasonId === null} onClick={() => reasonId !== null && onSubmit(reasonId, equipmentId)}>
          {t("restart.submit")}
        </button>
      }
    >
      <p>{t("restart.message")}</p>
      <div className="choice-grid">
        {reasons.map((r) => (
          <button key={r.id} type="button" className={`btn choice${r.id === reasonId ? " choice-selected" : ""}`} onClick={() => pickReason(r.id)}>
            {localName(lang, r.name, r.name_vi)}
            {r.id === reasonId && <span className="choice-note">{t("common.selected")}</span>}
          </button>
        ))}
      </div>
      {reason?.requires_equipment && (
        <>
          <p>{t("restart.pickEquipment")}</p>
          <EquipmentChoices equipment={equipment} selected={equipmentId} onSelect={setEquipmentId} allowNone />
        </>
      )}
    </Dialog>
  );
}

type ChoicesProps = { equipment: Equipment[]; selected: number | null; onSelect: (id: number | null) => void; allowNone?: boolean };

export function EquipmentChoices({ equipment, selected, onSelect, allowNone }: ChoicesProps) {
  const { t, lang } = useI18n();
  return (
    <div className="choice-grid">
      {allowNone && (
        <button type="button" className={`btn choice${selected === null ? " choice-selected" : ""}`} onClick={() => onSelect(null)}>
          {t("restart.noEquipment")}
        </button>
      )}
      {equipment.map((e) => (
        <button key={e.id} type="button" className={`btn choice${e.id === selected ? " choice-selected" : ""}`} onClick={() => onSelect(e.id)}>
          {localName(lang, e.name, e.name_vi)}
          {e.id === selected && <span className="choice-note">{t("common.selected")}</span>}
        </button>
      ))}
      {equipment.length === 0 && <p>{t("equipment.none")}</p>}
    </div>
  );
}
