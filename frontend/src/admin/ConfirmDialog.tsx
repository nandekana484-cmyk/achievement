// 確認のダイアログ(元に戻しにくい変更の前に出す)。最初に選ばれているボタンは「キャンセル」。Esc でもキャンセルになる。
import { useEffect, useRef } from "react";

type Props = { message: string; confirmLabel: string; cancelLabel: string; onConfirm: () => void; onCancel: () => void };

export function ConfirmDialog({ message, confirmLabel, cancelLabel, onConfirm, onCancel }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);
  return (
    <dialog ref={ref} className="admin-dialog" aria-label={message} onCancel={(e) => { e.preventDefault(); onCancel(); }}>
      <p>{message}</p>
      <div className="admin-dialog-buttons">
        <button type="button" className="admin-btn" autoFocus onClick={onCancel}>{cancelLabel}</button>
        <button type="button" className="admin-btn admin-danger" onClick={onConfirm}>{confirmLabel}</button>
      </div>
    </dialog>
  );
}
