// 「ひも付けの確認」: キッティングNo.でつながらない面1の計画のロットを、同じロットNo.・ファイルNo.の面2の計画に確定する。
// 「つながない(面1は書き出さない)」も選べる。確定したものも出し、やり直せる。詳細: docs/design/actuals-export.md
import { useState } from "react";
import { adminApi, useAdminCall } from "../adminApi";
import { at } from "../messages";
import { type LinkCheck, NO_LINK, initialChoice, linkKey } from "./actuals";

type Props = { checks: LinkCheck[]; onConfirmed: (message: string) => void; onError: (message: string) => void };

export function LinkChecks({ checks, onConfirmed, onError }: Props) {
  const call = useAdminCall();
  const [choices, setChoices] = useState<Record<string, string>>({});
  const choiceOf = (c: LinkCheck) => choices[linkKey(c)] ?? initialChoice(c);

  const confirm = async (c: LinkCheck) => {
    const choice = choiceOf(c);
    const r = await call(() => adminApi.POST("/api/admin/actuals/links", {
      body: { lot_no: c.lot_no, side1_kitting_no: c.side1_kitting_no, side2_kitting_no: choice === NO_LINK ? null : choice },
    }));
    if (r.ok) onConfirmed(at("links.confirmed", { kitting: c.side1_kitting_no, lot: c.lot_no }));
    else onError(r.message);
  };

  return (
    <section className="actuals-links" aria-label={at("links.title")}>
      <h2>{at("links.title")}</h2>
      <p className="admin-note">{at("links.note")}</p>
      <table className="admin-table" aria-label={at("links.title")}>
        <thead>
          <tr>
            <th>{at("actuals.col.lot")}</th><th>{at("actuals.col.file")}</th><th>{at("links.col.side1")}</th>
            <th>{at("links.col.state")}</th><th>{at("links.col.side2")}</th><th>{at("col.actions")}</th>
          </tr>
        </thead>
        <tbody>
          {checks.map((c) => (
            <tr key={linkKey(c)} className={c.state === "pending" ? "actuals-changed" : ""}>
              <td>{c.lot_no}</td><td>{c.file_no}</td>
              <td>
                {c.side1_kitting_no}
                <span className="actuals-total">
                  {at("links.issued", { date: c.side1_issue_date })} {c.side1_completed ? at("links.completed") : at("links.notCompleted")}
                </span>
              </td>
              <td>
                <strong>{at(c.state === "pending" ? "links.state.pending" : c.state === "confirmed" ? "links.state.confirmed" : "links.state.unlinked")}</strong>
                {c.decided_by && <span className="actuals-total">{at("links.decided", { who: c.decided_by, at: (c.decided_at ?? "").slice(0, 16).replace("T", " ") })}</span>}
              </td>
              <td>
                <select aria-label={at("links.choiceLabel", { kitting: c.side1_kitting_no, lot: c.lot_no })} value={choiceOf(c)}
                  onChange={(e) => setChoices({ ...choices, [linkKey(c)]: e.target.value })}>
                  {choiceOf(c) === "" && <option value="">{at("links.choose")}</option>}
                  {c.candidates.map((k) => (
                    <option key={k.kitting_no} value={k.kitting_no} disabled={k.paired_with !== null}>
                      {k.paired_with
                        ? at("links.candidatePaired", { kitting: k.kitting_no, partner: k.paired_with })
                        : at("links.candidate", { kitting: k.kitting_no, date: k.issue_date })}
                    </option>
                  ))}
                  <option value={NO_LINK}>{at("links.noLink")}</option>
                </select>
              </td>
              <td>
                <button type="button" className="admin-btn admin-primary" disabled={choiceOf(c) === ""} onClick={() => void confirm(c)}>
                  {at("links.confirm")}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
