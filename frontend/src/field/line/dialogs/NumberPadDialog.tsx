// 数を入れる画面(大きなテンキー)。生産の終了の生産数に使う。
// 送信が成功するまで閉じない。失敗したら理由を画面の中に出す(入力した数は消さない)。
import { useState } from "react";
import { Dialog } from "../../../shared/Dialog";
import { Keypad } from "./Keypad";
import { useSubmit } from "./useSubmit";

type Props = {
  title: string;
  message?: string;
  initial?: number | null;
  submitLabel: string;
  /** 送る。成功したら null、失敗したら理由の文を返す。 */
  onSubmit: (n: number) => Promise<string | null>;
  onCancel: () => void;
};

export function NumberPadDialog({ title, message, initial, submitLabel, onSubmit, onCancel }: Props) {
  const [text, setText] = useState(initial === null || initial === undefined ? "" : String(initial));
  const { sending, error, submit } = useSubmit();

  return (
    <Dialog
      title={title}
      onCancel={onCancel}
      actions={
        <button type="button" className="btn btn-primary" disabled={text === "" || sending} onClick={() => submit(() => onSubmit(Number(text)))}>
          {sending ? "送信中…" : submitLabel}
        </button>
      }
    >
      {message && <p>{message}</p>}
      {error && <p className="dialog-error" role="alert"><span className="notice-kind">エラー</span> {error}</p>}
      <Keypad text={text} onChange={setText} disabled={sending} />
    </Dialog>
  );
}
