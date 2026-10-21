// 数を入れる画面(大きなテンキー)。生産の終了の生産数と、NG数に使う。
// 送信が成功するまで閉じない。失敗したら理由を画面の中に出す(入力した数は消さない)。
import { useState } from "react";
import { Dialog } from "../../../shared/Dialog";

type Props = {
  title: string;
  message?: string;
  initial?: number | null;
  submitLabel: string;
  /** 送る。成功したら null、失敗したら理由の文を返す。 */
  onSubmit: (n: number) => Promise<string | null>;
  onCancel: () => void;
};

const KEYS = ["7", "8", "9", "4", "5", "6", "1", "2", "3", "0", "00"];
const MAX_DIGITS = 6;

export function NumberPadDialog({ title, message, initial, submitLabel, onSubmit, onCancel }: Props) {
  const [text, setText] = useState(initial === null || initial === undefined ? "" : String(initial));
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const press = (k: string) => setText((t) => (t + k).replace(/^0+(?=\d)/, "").slice(0, MAX_DIGITS));

  const submit = async () => {
    setSending(true);
    setError(null);
    const failure = await onSubmit(Number(text));
    setSending(false);
    if (failure) setError(failure); // 成功したときは呼び出し側が閉じる
  };

  return (
    <Dialog
      title={title}
      onCancel={onCancel}
      actions={
        <button type="button" className="btn btn-primary" disabled={text === "" || sending} onClick={submit}>
          {sending ? "送信中…" : submitLabel}
        </button>
      }
    >
      {message && <p>{message}</p>}
      {error && (
        <p className="dialog-error" role="alert">
          <span className="notice-kind">エラー</span> {error}
        </p>
      )}
      <output className="pad-display" aria-label="入力した数">{text === "" ? "—" : text}</output>
      <div className="pad">
        {KEYS.map((k) => (
          <button key={k} type="button" className="btn pad-key" disabled={sending} onClick={() => press(k)}>
            {k}
          </button>
        ))}
        <button type="button" className="btn pad-key" disabled={sending} onClick={() => setText((t) => t.slice(0, -1))} aria-label="1文字消す">
          ←
        </button>
        <button type="button" className="btn pad-key pad-clear" disabled={sending} onClick={() => setText("")}>
          クリア
        </button>
      </div>
    </Dialog>
  );
}
