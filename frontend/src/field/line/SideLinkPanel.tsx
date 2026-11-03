// 面1と面2の紐づけ(現場の画面)。2回目(面2)の計画に、1回目のキッティングNo.の欄と「紐づける」ボタンを出す。
// 1回目の画面には、紐づいた2回目を表示するだけ。保存の前に、合わないロットと書き出し済みを確かめる。詳細: docs/design/actuals-export.md
import { useState } from "react";
import { useI18n } from "../../i18n/I18nProvider";
import { api, type BoardPlan } from "../../shared/api";
import { Dialog } from "../../shared/Dialog";
import { failureMessage, sendWithRetry } from "../../shared/send";
import type { Operation } from "../../shared/useOperation";
import { canSubmit, confirmLines, panelState, type SideLinkCheck, unlinkLines } from "./sideLink";

type Props = { plan: BoardPlan; op: Operation; requireOperator: (action: () => void) => () => void };
type Ask = { title: string; lines: string[]; confirmLabel: string; run: () => void };

export function SideLinkPanel({ plan, op, requireOperator }: Props) {
  const { t } = useI18n();
  const v = plan.side_link;
  if (!v) return null;
  const state = panelState(v);
  if (state.mode === "side1") {
    return state.partner ? <p className="side-link">{t("sideLink.side1Partner", { partner: state.partner })}</p> : null;
  }
  return <Side2Panel key={`${plan.plan.kitting_no}:${v.partner}:${v.suggested}`} plan={plan} op={op} requireOperator={requireOperator} />;
}

function Side2Panel({ plan, op, requireOperator }: Props) {
  const { t } = useI18n();
  const kno = plan.plan.kitting_no;
  const state = panelState(plan.side_link!);
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(state.mode === "input" ? state.initial : "");
  const [ask, setAsk] = useState<Ask | null>(null);
  const [error, setError] = useState<string | null>(null);
  const options = state.mode === "side1" ? [] : state.options;
  const showInput = state.mode === "input" || editing;

  const send = async (body: string, confirmLot: boolean) => {
    setAsk(null);
    const r = await op.run(`sideLink:${kno}`, { body, confirmLot }, (request_id) =>
      api.POST("/api/runs/{kitting_no}/side-link", { params: { path: { kitting_no: kno } }, body: { request_id, side1_kitting_no: body, confirm_lot_mismatch: confirmLot } }), { showError: false });
    if (r.ok) setEditing(false);
    else setError(r.message);
  };

  const submit = requireOperator(async () => {
    setError(null);
    const out = await sendWithRetry<SideLinkCheck>(() =>
      api.POST("/api/runs/{kitting_no}/side-link/check", { params: { path: { kitting_no: kno } }, body: { side1_kitting_no: text } }));
    if (!out.ok) return setError(failureMessage(out, t));
    if (out.data.errors.length > 0) return setError(out.data.errors[0]);
    const lines = confirmLines(out.data, t);
    const go = () => void send(text, out.data.mismatched_lots.length > 0);
    if (lines.length === 0) go();
    else setAsk({ title: t("sideLink.confirmTitle"), lines, confirmLabel: t("sideLink.confirm"), run: go });
  });

  const unlink = requireOperator(async () => {
    setError(null);
    const out = await sendWithRetry<SideLinkCheck>(() =>
      api.POST("/api/runs/{kitting_no}/side-link/check", { params: { path: { kitting_no: kno } }, body: { side1_kitting_no: state.mode === "linked" ? state.partner : "" } }));
    const exported = out.ok && out.data.exported;
    setAsk({
      title: t("sideLink.confirmTitle"), lines: unlinkLines(exported, t), confirmLabel: t("sideLink.unlink"),
      run: () => {
        setAsk(null);
        void op.run(`sideUnlink:${kno}`, {}, (request_id) =>
          api.POST("/api/runs/{kitting_no}/side-link/unlink", { params: { path: { kitting_no: kno } }, body: { request_id } }), { showError: false })
          .then((r) => (r.ok ? setError(null) : setError(r.message)));
      },
    });
  });

  return (
    <div className="side-link" aria-label={t("sideLink.title")}>
      <div className="side-link-title">{t("sideLink.title")}</div>
      {state.mode === "linked" && !editing && (
        <p className="side-link-partner">
          {t("sideLink.linkedTo", { partner: state.partner })}
          <span className="side-link-by"> {t("sideLink.by", { who: plan.side_link?.decided_by ?? "", source: t(`sideLink.source.${state.source === "admin" ? "admin" : "field"}`) })}</span>
        </p>
      )}
      {showInput && (
        <div className="side-link-row">
          <input aria-label={t("sideLink.inputLabel")} value={text} onChange={(e) => setText(e.target.value)} autoComplete="off" />
          {options.length > 1 && (
            <select aria-label={t("sideLink.pick")} value="" onChange={(e) => e.target.value && setText(e.target.value)}>
              <option value="">{t("sideLink.pick")}</option>
              {options.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          )}
          <button type="button" className="btn btn-primary" disabled={!canSubmit(text) || op.isBusy(`sideLink:${kno}`)} onClick={submit}>
            {t("sideLink.link")}
          </button>
          {editing && <button type="button" className="btn" onClick={() => setEditing(false)}>{t("common.cancel")}</button>}
        </div>
      )}
      {state.mode === "input" && state.autoNote && <p className="side-link-note">{t("sideLink.autoNote")}</p>}
      {state.mode === "linked" && !editing && (
        <div className="side-link-row">
          <button type="button" className="btn" onClick={() => { setText(state.partner); setEditing(true); }}>{t("sideLink.fix")}</button>
          <button type="button" className="btn" disabled={op.isBusy(`sideUnlink:${kno}`)} onClick={unlink}>{t("sideLink.unlink")}</button>
        </div>
      )}
      {error && <p className="plan-warning" role="alert">{error}</p>}
      {ask && (
        <Dialog title={ask.title} onCancel={() => setAsk(null)} actions={<button type="button" className="btn btn-primary" onClick={ask.run}>{ask.confirmLabel}</button>}>
          {ask.lines.map((l) => <p key={l} className="confirm-message">{l}</p>)}
        </Dialog>
      )}
    </div>
  );
}
