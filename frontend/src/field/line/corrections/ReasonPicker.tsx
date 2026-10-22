// 訂正の理由(押し間違い・押し忘れ・数の入力の誤り・その他)と、内容の記入(その他では必須)。
import { useI18n } from "../../../i18n/I18nProvider";
import type { MessageKey } from "../../../i18n/ja";

export const CORRECTION_REASONS = ["mistake", "forgot", "wrong_qty", "other"] as const;
export type CorrectionReason = (typeof CORRECTION_REASONS)[number];

export const REASON_KEYS: Record<string, MessageKey> = {
  mistake: "correctionReason.mistake",
  forgot: "correctionReason.forgot",
  wrong_qty: "correctionReason.wrong_qty",
  other: "correctionReason.other",
};

/** 理由が選ばれていて、その他なら内容が書かれているか。 */
export function reasonReady(reason: CorrectionReason | null, note: string): reason is CorrectionReason {
  return reason !== null && (reason !== "other" || note.trim() !== "");
}

type Props = {
  reason: CorrectionReason | null;
  note: string;
  onReason: (r: CorrectionReason) => void;
  onNote: (text: string) => void;
  disabled?: boolean;
};

export function ReasonPicker({ reason, note, onReason, onNote, disabled }: Props) {
  const { t } = useI18n();
  return (
    <div className="reason-picker">
      <p className="fix-section-title">{t("correction.reason")}</p>
      <div className="fix-reasons" role="group" aria-label={t("correction.reason")}>
        {CORRECTION_REASONS.map((r) => (
          <button key={r} type="button" className={`btn choice${r === reason ? " choice-selected" : ""}`} disabled={disabled}
            aria-pressed={r === reason} onClick={() => onReason(r)}>
            {t(REASON_KEYS[r])}
          </button>
        ))}
      </div>
      {reason === "other" && (
        <label className="field-label">
          {t("correction.note")}
          <textarea className="text-input" rows={2} maxLength={2000} value={note} disabled={disabled}
            onChange={(e) => onNote(e.target.value)} />
        </label>
      )}
    </div>
  );
}
