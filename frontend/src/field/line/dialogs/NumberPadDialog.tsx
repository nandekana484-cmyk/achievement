// 数を入れる画面(大きなテンキー)。生産の終了の生産数と、NG数に使う。
import { useState } from "react";
import { Dialog } from "../../../shared/Dialog";

type Props = { title: string; message?: string; initial?: number | null; submitLabel: string; onSubmit: (n: number) => void; onCancel: () => void };

const KEYS = ["7", "8", "9", "4", "5", "6", "1", "2", "3", "0", "00"];
const MAX_DIGITS = 6;

export function NumberPadDialog({ title, message, initial, submitLabel, onSubmit, onCancel }: Props) {
  const [text, setText] = useState(initial === null || initial === undefined ? "" : String(initial));
  const press = (k: string) => setText((t) => (t + k).replace(/^0+(?=\d)/, "").slice(0, MAX_DIGITS));

  return (
    <Dialog
      title={title}
      onCancel={onCancel}
      actions={
        <button type="button" className="btn btn-primary" disabled={text === ""} onClick={() => onSubmit(Number(text))}>
          {submitLabel}
        </button>
      }
    >
      {message && <p>{message}</p>}
      <output className="pad-display" aria-label="入力した数">{text === "" ? "—" : text}</output>
      <div className="pad">
        {KEYS.map((k) => (
          <button key={k} type="button" className="btn pad-key" onClick={() => press(k)}>
            {k}
          </button>
        ))}
        <button type="button" className="btn pad-key" onClick={() => setText((t) => t.slice(0, -1))} aria-label="1文字消す">
          ←
        </button>
        <button type="button" className="btn pad-key pad-clear" onClick={() => setText("")}>
          クリア
        </button>
      </div>
    </Dialog>
  );
}
