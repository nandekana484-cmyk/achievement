// NG数の入力: ロットを選ぶ → NGが出た面を選ぶ(選べない面は押せない) → テンキーで数を入れる。
// 入力済みのNG(ロット・面・数)も一覧で見られる。送信が成功するまで閉じない。
import { useState } from "react";
import { useI18n } from "../../../i18n/I18nProvider";
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
  const { t } = useI18n();
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
      title={t("ng.title")}
      wide
      onCancel={onCancel}
      actions={
        <button type="button" className="btn btn-primary" disabled={!lotNo || side === null || text === "" || sending}
          onClick={() => lotNo && side !== null && submit(() => onSubmit(lotNo, side, Number(text)))}>
          {sending ? t("common.sending") : t("ng.submit")}
        </button>
      }
    >
      {error && <p className="dialog-error" role="alert"><span className="notice-kind">{t("notice.error")}</span> {error}</p>}
      <div className="ng-layout">
        <div className="ng-steps">
          <p className="ng-step-title">{t("ng.stepLot")}</p>
          <div className="choice-grid ng-lots" role="group" aria-label={t("ng.lotGroup")}>
            {lots.map((lot) => (
              <button key={lot.lot_no} type="button" className={`btn choice${lot.lot_no === lotNo ? " choice-selected" : ""}`}
                onClick={() => pickLot(lot.lot_no)}>
                {lot.lot_no}
                <span className="choice-sub">{t("ng.lotSub", { name: lot.product_name, qty: t("unit.sheets", { count: lot.planned_qty }) })}</span>
                {lot.lot_no === lotNo && <span className="choice-note">{t("common.selected")}</span>}
              </button>
            ))}
          </div>
          <p className="ng-step-title">{t("ng.stepSide")}</p>
          <div className="choice-grid" role="group" aria-label={t("ng.sideGroup")}>
            {[1, 2].map((s) => (
              <button key={s} type="button" className={`btn choice${s === side ? " choice-selected" : ""}`}
                disabled={!choice || !choice.sides.includes(s)} onClick={() => pickSide(s)}>
                {t("ng.side", { side: s })}
                {s === side && <span className="choice-note">{t("common.selected")}</span>}
                {choice && !choice.sides.includes(s) && <span className="choice-sub">{t("ng.notSelectable")}</span>}
              </button>
            ))}
          </div>
          {choice?.note && <p className="ng-note">{choice.note}</p>}
          <NgEntries plan={plan} />
        </div>
        <div className="ng-pad">
          <p className="ng-step-title">{lotNo && side !== null ? t("ng.stepQtyFor", { lot: lotNo, side }) : t("ng.stepQty")}</p>
          <Keypad text={text} onChange={setText} disabled={sending || !lotNo || side === null} />
        </div>
      </div>
    </Dialog>
  );
}

function NgEntries({ plan }: { plan: BoardPlan }) {
  const { t } = useI18n();
  return (
    <div className="ng-entries">
      <p className="ng-step-title">{t("ng.entries")}</p>
      {plan.ng_entries.length === 0 ? (
        <p className="ng-note">{t("ng.noEntries")}</p>
      ) : (
        <ul aria-label={t("ng.entries")}>
          {plan.ng_entries.map((n) => (
            <li key={`${n.lot_no}:${n.side}`}>{t("ng.entry", { lot: n.lot_no, side: n.side, qty: n.ng_qty })}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
