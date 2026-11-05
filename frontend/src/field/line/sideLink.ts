// 面1と面2の紐づけ(現場の画面)の、欄・候補・確認の文の決め方。画面から切り離した処理(vitest でテストする)。詳細: docs/design/actuals-export.md
import type { Translate } from "../../i18n/translate";
import type { BoardPlan } from "../../shared/api";
import type { components } from "../../api/schema";

export type SideLinkView = NonNullable<BoardPlan["side_link"]>;
export type SideLinkCheck = components["schemas"]["SideLinkCheckOut"];

export type PanelState =
  | { mode: "side1"; partner: string | null }
  | { mode: "linked"; partner: string; source: string; options: string[] }
  | { mode: "input"; initial: string; options: string[]; autoNote: boolean };

/** 欄の状態。紐づけ済みなら相手と「直す」「外す」、無ければ候補を最初から入れた欄(候補が複数なら空欄にして、一覧から選ぶ)。 */
export function panelState(v: SideLinkView): PanelState {
  if (v.role === "side1") return { mode: "side1", partner: v.partner };
  if (v.partner) return { mode: "linked", partner: v.partner, source: v.partner_source ?? "field", options: v.candidates };
  return { mode: "input", initial: v.suggested ?? "", options: v.candidates.length > 1 ? v.candidates : [], autoNote: v.partner_source === "h" };
}

/** 保存の前に出す確認の文(合わないロットの警告と、書き出し済みの確認)。無ければ、確認なしで保存する。 */
export function confirmLines(chk: Pick<SideLinkCheck, "mismatched_lots" | "exported">, t: Translate): string[] {
  const lines: string[] = [];
  if (chk.mismatched_lots.length > 0) lines.push(t("sideLink.lotMismatch", { lots: chk.mismatched_lots.join(t("sideLink.separator")) }));
  if (chk.exported) lines.push(t("sideLink.exported"));
  return lines;
}

/** 外す前に出す確認の文(書き出し済みなら、その注意)。 */
export function unlinkLines(exported: boolean, t: Translate): string[] {
  return [t("sideLink.unlinkAsk"), ...(exported ? [t("sideLink.exported")] : [])];
}

export const canSubmit = (text: string) => text.trim().length > 0;

/** 紐づけのページの URL(2回目のキッティングNo.)。back は戻る先(/field/ から始まる URL だけ。無ければ、その計画を選んだライン画面)。 */
export function linkPageUrl(side2KittingNo: string, back?: string): string {
  return `/field/link/${encodeURIComponent(side2KittingNo)}${back ? `?back=${encodeURIComponent(back)}` : ""}`;
}

/** 戻る先として受け付ける URL(同じアプリの /field/ の中だけ)。 */
export function safeBack(back: string | null): string | null {
  return back !== null && /^\/field\/[^/]/.test(back) && !back.includes("//") ? back : null;
}

/** 紐づけのボタンに出す今の状態。 */
export function linkButtonState(v: Pick<SideLinkView, "partner">): "linked" | "unlinked" {
  return v.partner ? "linked" : "unlinked";
}
