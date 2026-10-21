// 文字を入れる画面(備考)。
import { useState } from "react";
import { Dialog } from "../../../shared/Dialog";

type Props = { title: string; label: string; submitLabel: string; onSubmit: (text: string) => void; onCancel: () => void };

export function TextDialog({ title, label, submitLabel, onSubmit, onCancel }: Props) {
  const [text, setText] = useState("");
  return (
    <Dialog
      title={title}
      onCancel={onCancel}
      actions={
        <button type="button" className="btn btn-primary" disabled={!text.trim()} onClick={() => onSubmit(text.trim())}>
          {submitLabel}
        </button>
      }
    >
      <label className="field-label">
        {label}
        <textarea className="text-input" rows={4} maxLength={2000} value={text} onChange={(e) => setText(e.target.value)} autoFocus />
      </label>
    </Dialog>
  );
}
