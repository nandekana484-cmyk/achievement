// 紐づけのページの本体(AD-19 と同じ): 1回目のキッティングNo.の欄と候補、作業者ID、「紐づける」(確かめてから保存)、直す、外す。
// 作業者IDは親(LinkPage)が持つので、紐づけたあとにこの部品をつくり直しても消えない。保存の前に、合わないロットと書き出し済みを確かめる。規則とAPIは AD-19 のまま。詳細: docs/design/actuals-export.md
import { useState } from "react";
import { useI18n } from "../../i18n/I18nProvider";
import { api } from "../../shared/api";
import { Dialog } from "../../shared/Dialog";
import { failureMessage, sendWithRetry } from "../../shared/send";
import { uuidv4 } from "../../shared/uuid";
import { canSubmit, confirmLines, panelState, type SideLinkCheck, type SideLinkView, unlinkLines } from "../line/sideLink";

type Props = { kittingNo: string; view: SideLinkView; onView: (v: SideLinkView) => void; workerId: string; onWorkerId: (v: string) => void };
type Ask = { lines: string[]; confirmLabel: string; run: () => void };

export function LinkForm({ kittingNo, view, onView, workerId, onWorkerId }: Props) {
  const { t } = useI18n();
  const state = panelState(view);
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(state.mode === "input" ? state.initial : "");
  const [ask, setAsk] = useState<Ask | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const options = state.mode === "side1" ? [] : state.options;
  const showInput = state.mode === "input" || editing;
  const hasWorker = workerId.trim() !== "";
  const path = { params: { path: { kitting_no: kittingNo } } };

  const check = (side1: string) =>
    sendWithRetry<SideLinkCheck>(() => api.POST("/api/runs/{kitting_no}/side-link/check", { ...path, body: { side1_kitting_no: side1 } }));

  const save = async (side1: string, confirmLot: boolean) => {
    setAsk(null);
    setBusy(true);
    const body = { request_id: uuidv4(), worker_id: workerId.trim(), side1_kitting_no: side1, confirm_lot_mismatch: confirmLot };
    const r = await sendWithRetry(() => api.POST("/api/runs/{kitting_no}/side-link", { ...path, body }));
    setBusy(false);
    if (!r.ok) return setError(failureMessage(r, t));
    setError(null);
    setEditing(false);
    onView(r.data);
  };

  const submit = async () => {
    setError(null);
    const out = await check(text);
    if (!out.ok) return setError(failureMessage(out, t));
    if (out.data.errors.length > 0) return setError(out.data.errors[0]);
    const lines = confirmLines(out.data, t);
    const go = () => void save(text, out.data.mismatched_lots.length > 0);
    if (lines.length === 0) go();
    else setAsk({ lines, confirmLabel: t("sideLink.confirm"), run: go });
  };

  const unlink = async () => {
    setError(null);
    const out = await check(state.mode === "linked" ? state.partner : "");
    setAsk({
      lines: unlinkLines(out.ok && out.data.exported, t), confirmLabel: t("sideLink.unlink"),
      run: async () => {
        setAsk(null);
        setBusy(true);
        const r = await sendWithRetry(() => api.POST("/api/runs/{kitting_no}/side-link/unlink", { ...path, body: { request_id: uuidv4(), worker_id: workerId.trim() } }));
        setBusy(false);
        if (!r.ok) return setError(failureMessage(r, t));
        setError(null);
        onView(r.data);
      },
    });
  };

  return (
    <div className="side-link link-form" aria-label={t("sideLink.title")}>
      <div className="side-link-title">{t("sideLink.title")}</div>
      {state.mode === "linked" && !editing && (
        <p className="side-link-partner">
          {t("sideLink.linkedTo", { partner: state.partner })}
          <span className="side-link-by"> {t("sideLink.by", { who: view.decided_by ?? "", source: t(`sideLink.source.${state.source === "admin" ? "admin" : "field"}`) })}</span>
        </p>
      )}
      <label className="link-worker">{t("link.workerId")}
        <input value={workerId} onChange={(e) => onWorkerId(e.target.value)} autoComplete="off" />
      </label>
      {showInput && (
        <div className="side-link-row">
          <input aria-label={t("sideLink.inputLabel")} value={text} onChange={(e) => setText(e.target.value)} autoComplete="off" />
          {options.length > 1 && (
            <select aria-label={t("sideLink.pick")} value="" onChange={(e) => e.target.value && setText(e.target.value)}>
              <option value="">{t("sideLink.pick")}</option>
              {options.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          )}
          <button type="button" className="btn btn-primary" disabled={!canSubmit(text) || !hasWorker || busy} onClick={() => void submit()}>{t("sideLink.link")}</button>
          {editing && <button type="button" className="btn" onClick={() => setEditing(false)}>{t("common.cancel")}</button>}
        </div>
      )}
      {state.mode === "input" && state.autoNote && <p className="side-link-note">{t("sideLink.autoNote")}</p>}
      {state.mode === "linked" && !editing && (
        <div className="side-link-row">
          <button type="button" className="btn" disabled={busy} onClick={() => { setText(state.partner); setEditing(true); }}>{t("sideLink.fix")}</button>
          <button type="button" className="btn" disabled={!hasWorker || busy} onClick={() => void unlink()}>{t("sideLink.unlink")}</button>
        </div>
      )}
      {error && <p className="plan-warning" role="alert">{error}</p>}
      {ask && (
        <Dialog title={t("sideLink.confirmTitle")} onCancel={() => setAsk(null)} actions={<button type="button" className="btn btn-primary" onClick={ask.run}>{ask.confirmLabel}</button>}>
          {ask.lines.map((l) => <p key={l} className="confirm-message">{l}</p>)}
        </Dialog>
      )}
    </div>
  );
}
