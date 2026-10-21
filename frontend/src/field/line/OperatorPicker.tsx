// 今の担当者を選ぶ画面。
import type { Operator } from "../../shared/api";
import { Dialog } from "../../shared/Dialog";

type Props = { operators: Operator[]; currentId: number | null; onPick: (id: number) => void; onCancel: () => void };

export function OperatorPicker({ operators, currentId, onPick, onCancel }: Props) {
  return (
    <Dialog title="担当者の交代" onCancel={onCancel}>
      <p>このラインの今の担当者を選んでください。ボタン操作の記録に自動で付きます。</p>
      <div className="choice-grid">
        {operators.map((o) => (
          <button key={o.id} type="button" className={`btn choice${o.id === currentId ? " choice-selected" : ""}`} onClick={() => onPick(o.id)}>
            {o.name}
            {o.id === currentId && <span className="choice-note">今の担当者</span>}
          </button>
        ))}
      </div>
      {operators.length === 0 && <p>作業者が登録されていません。</p>}
    </Dialog>
  );
}
