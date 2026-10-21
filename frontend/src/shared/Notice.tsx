// 画面の上に出すお知らせ(エラーと案内)。色だけでなく「エラー」「お知らせ」の文字でも区別する。
import type { ReactNode } from "react";
import { useI18n } from "../i18n/I18nProvider";

type Props = { kind: "error" | "info"; children: ReactNode; onClose?: () => void; action?: ReactNode };

export function Notice({ kind, children, onClose, action }: Props) {
  const { t } = useI18n();
  return (
    <div className={`notice notice-${kind}`} role={kind === "error" ? "alert" : "status"}>
      <span className="notice-kind">{kind === "error" ? t("notice.error") : t("notice.info")}</span>
      <span className="notice-text">{children}</span>
      {action}
      {onClose && (
        <button type="button" className="btn btn-small" onClick={onClose}>
          {t("common.close")}
        </button>
      )}
    </div>
  );
}
