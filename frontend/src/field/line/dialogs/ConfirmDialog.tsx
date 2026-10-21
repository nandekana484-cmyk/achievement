// 送る前に確かめる画面(片付けの終了など)。
import { Dialog } from "../../../shared/Dialog";

type Props = { title: string; message: string; confirmLabel: string; onConfirm: () => void; onCancel: () => void };

export function ConfirmDialog({ title, message, confirmLabel, onConfirm, onCancel }: Props) {
  return (
    <Dialog
      title={title}
      onCancel={onCancel}
      actions={
        <button type="button" className="btn btn-primary" onClick={onConfirm}>
          {confirmLabel}
        </button>
      }
    >
      <p className="confirm-message">{message}</p>
    </Dialog>
  );
}
