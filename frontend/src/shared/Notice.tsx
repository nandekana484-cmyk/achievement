// 画面の上に出すお知らせ(エラーと案内)。色だけでなく「エラー」「お知らせ」の文字でも区別する。
import type { ReactNode } from "react";

type Props = { kind: "error" | "info"; children: ReactNode; onClose?: () => void; action?: ReactNode };

export function Notice({ kind, children, onClose, action }: Props) {
  return (
    <div className={`notice notice-${kind}`} role={kind === "error" ? "alert" : "status"}>
      <span className="notice-kind">{kind === "error" ? "エラー" : "お知らせ"}</span>
      <span className="notice-text">{children}</span>
      {action}
      {onClose && (
        <button type="button" className="btn btn-small" onClick={onClose}>
          閉じる
        </button>
      )}
    </div>
  );
}
