// NG数の入力: ロットを選ぶ → NGが出た面を選ぶ(選べない面は押せない) → テンキーで数を入れる。
// 入力済みのNG(ロット・面・数)も一覧で見られる。送信が成功するまで閉じない。
import { useState } from "react";
import type { BoardPlan } from "../../../shared/api";
import { Dialog } from "../../../shared/Dialog";
import { Keypad } from "./Keypad";
import { useSubmit } from "./useSubmit";

type Props = {
  plan: BoardPlan;
  /** 送る。成功したら null、失敗したら理由の文を返す。 */
  onSubmit: (lotNo: string, side: number, n: number) => Promise<string | null>;
  onCancel: () => void;
};

export function NgDialog({ plan, onSubmit, onCancel }: Props) {
  const lots = plan.plan.lots;
  const [lotNo, setLotNo] = useState<string | null>(lots.length === 1 ? lots[0].lot_no : null);
  const [side, setSide] = useState<number | null>(null);
  const [text, setText] = useState("");
  const { sending, error, submit } = useSubmit();
  const choice = plan.ng_choices.find((c) => c.lot_no === lotNo);
  const current = (lot: string, s: number) => plan.ng_entries.find((n) => n.lot_no === lot && n.side === s)?.ng_qty;

  const pickLot = (lot: string) => {
    setLotNo(lot);
    setSide(null);
    setText("");
  };
  const pickSide = (s: number) => {
    setSide(s);
    const now = lotNo ? current(lotNo, s) : undefined;
    setText(now === undefined ? "" : String(now));
  };

  return (
    <Dialog
      title="NG数の入力"
      wide
      onCancel={onCancel}
      actions={
        <button type="button" className="btn btn-primary" disabled={!lotNo || side === null || text === "" || sending}
          onClick={() => lotNo && side !== null && submit(() => onSubmit(lotNo, side, Number(text)))}>
          {sending ? "送信中…" : "NG数を記録"}
        </button>
      }
    >
      {error && <p className="dialog-error" role="alert"><span className="notice-kind">エラー</span> {error}</p>}
      <div className="ng-layout">
        <div className="ng-steps">
          <p className="ng-step-title">1. ロットを選ぶ</p>
          <div className="choice-grid ng-lots" role="group" aria-label="ロット">
            {lots.map((lot) => (
              <button key={lot.lot_no} type="button" className={`btn choice${lot.lot_no === lotNo ? " choice-selected" : ""}`}
                onClick={() => pickLot(lot.lot_no)}>
                {lot.lot_no}
                <span className="choice-sub">{lot.product_name}・{lot.planned_qty}枚</span>
                {lot.lot_no === lotNo && <span className="choice-note">選択中</span>}
              </button>
            ))}
          </div>
          <p className="ng-step-title">2. NGが出た面を選ぶ</p>
          <div className="choice-grid" role="group" aria-label="面">
            {[1, 2].map((s) => (
              <button key={s} type="button" className={`btn choice${s === side ? " choice-selected" : ""}`}
                disabled={!choice || !choice.sides.includes(s)} onClick={() => pickSide(s)}>
                面{s}
                {s === side && <span className="choice-note">選択中</span>}
                {choice && !choice.sides.includes(s) && <span className="choice-sub">選べません</span>}
              </button>
            ))}
          </div>
          {choice?.note && <p className="ng-note">{choice.note}</p>}
          <NgEntries plan={plan} />
        </div>
        <div className="ng-pad">
          <p className="ng-step-title">3. NG数を入れる{lotNo && side !== null ? `(${lotNo}・面${side})` : ""}</p>
          <Keypad text={text} onChange={setText} disabled={sending || !lotNo || side === null} />
        </div>
      </div>
    </Dialog>
  );
}

function NgEntries({ plan }: { plan: BoardPlan }) {
  return (
    <div className="ng-entries">
      <p className="ng-step-title">入力済みのNG</p>
      {plan.ng_entries.length === 0 ? (
        <p className="ng-note">まだありません</p>
      ) : (
        <ul aria-label="入力済みのNG">
          {plan.ng_entries.map((n) => (
            <li key={`${n.lot_no}:${n.side}`}>{n.lot_no}・面{n.side}: {n.ng_qty}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
