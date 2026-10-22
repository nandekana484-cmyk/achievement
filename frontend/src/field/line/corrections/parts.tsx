// 訂正の画面で共通に使う部品(記録を選ぶボタン、下の操作のボタン、失敗の理由)。
import { useI18n } from "../../../i18n/I18nProvider";
import { formatHM } from "../timeScale";

type Choice = { id: number; label: string; start_at: string; end_at?: string | null };

/** 直す記録を選ぶボタン(名前と時刻)。 */
export function RecordChoices({ items, selectedId, disabled, onPick }: {
  items: Choice[]; selectedId: number | null; disabled: boolean; onPick: (id: number) => void;
}) {
  const { t } = useI18n();
  return (
    <div className="fix-records" role="group" aria-label={t("correction.recordAria")}>
      {items.map((c) => (
        <button key={c.id} type="button" className={`btn choice${c.id === selectedId ? " choice-selected" : ""}`}
          aria-pressed={c.id === selectedId} disabled={disabled} onClick={() => onPick(c.id)}>
          {c.label}
          <span className="choice-sub">{c.end_at ? t("step.timeRange", { start: formatHM(c.start_at), end: formatHM(c.end_at) })
            : t("step.timeOpen", { start: formatHM(c.start_at) })}</span>
        </button>
      ))}
    </div>
  );
}

type ActionsProps = {
  voiding: boolean;
  setVoiding: (v: boolean) => void;
  sending: boolean;
  hasTarget: boolean;
  ready: boolean; // 理由が選ばれている
  onSend: () => void;
};

/** 下の操作のボタン。ふだんは「この記録を取り消す」「訂正を記録」、取り消しの確認では「戻る」「取り消す」。 */
export function FixActions({ voiding, setVoiding, sending, hasTarget, ready, onSend }: ActionsProps) {
  const { t } = useI18n();
  if (voiding) {
    return (
      <>
        <button type="button" className="btn btn-secondary" disabled={sending} onClick={() => setVoiding(false)}>{t("correction.back")}</button>
        <button type="button" className="btn btn-danger" disabled={sending || !ready} onClick={onSend}>
          {sending ? t("common.sending") : t("correction.voidSubmit")}
        </button>
      </>
    );
  }
  return (
    <>
      <button type="button" className="btn btn-end" disabled={sending || !hasTarget} onClick={() => setVoiding(true)}>{t("correction.void")}</button>
      <button type="button" className="btn btn-primary" disabled={sending || !hasTarget || !ready} onClick={onSend}>
        {sending ? t("common.sending") : t("correction.submit")}
      </button>
    </>
  );
}

export function ErrorLine({ error }: { error: string | null }) {
  const { t } = useI18n();
  return error ? <p className="dialog-error" role="alert"><span className="notice-kind">{t("notice.error")}</span> {error}</p> : null;
}
