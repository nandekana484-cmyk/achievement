// ダイアログの土台。画面の中央に出し、背景を押しても閉じない(押し間違いを防ぐ)。
import type { ReactNode } from "react";
import { useI18n } from "../i18n/I18nProvider";

type Props = {
  title: string;
  children: ReactNode;
  onCancel: () => void;
  actions?: ReactNode;
  wide?: boolean;
  cancelLabel?: string; // 見るだけの画面では「閉じる」にする
};

export function Dialog({ title, children, onCancel, actions, wide, cancelLabel }: Props) {
  const { t } = useI18n();
  return (
    <div className="dialog-backdrop">
      <div className={`dialog${wide ? " dialog-wide" : ""}`} role="dialog" aria-modal="true" aria-label={title}>
        <h2 className="dialog-title">{title}</h2>
        <div className="dialog-body">{children}</div>
        <div className="dialog-actions">
          <button type="button" className="btn btn-secondary" onClick={onCancel}>
            {cancelLabel ?? t("common.cancel")}
          </button>
          {actions}
        </div>
      </div>
    </div>
  );
}
