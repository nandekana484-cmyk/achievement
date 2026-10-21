// 工程の並び・名前・色と、工程の状態の判定(開発指針 5.4)。
import type { RunEvent, StepType } from "../../shared/api";
import { formatHM } from "./timeScale";

export const STEP_ORDER: StepType[] = ["setup", "n1_check", "production", "first_article", "xray", "cleanup"];

export const STEP_LABELS: Record<StepType, string> = {
  setup: "段取り",
  n1_check: "N1チェック",
  production: "生産",
  first_article: "初品チェック",
  xray: "X線検査",
  cleanup: "片付け",
};

// 色だけで区別しないよう、表示では必ず工程名も出す
export const STEP_COLORS: Record<StepType, string> = {
  setup: "#8250df",
  n1_check: "#0969da",
  production: "#1a7f37",
  first_article: "#bf8700",
  xray: "#cf222e",
  cleanup: "#57606a",
};

export type StepState = "todo" | "doing" | "done";

export const STATE_TEXT: Record<StepState, string> = { todo: "未着手", doing: "作業中", done: "済" };

export type StepStatus = {
  step: StepType;
  state: StepState;
  label: string; // 生産は「生産 1回目」のように区切りの番号を付ける
  timeText: string;
  open: RunEvent | null; // 終了していない記録
  nextSeq: number; // 次に開始したときの区切りの番号
  action: "start" | "end";
  needsQty: boolean; // 生産の終了: 生産数を入れる
  needsReason: boolean; // 生産の2回目以降の開始: 再開理由を選ぶ
  needsConfirm: boolean; // 片付けの終了: 完了になることを確認する
};

/** その計画の工程の記録から、工程の状態と、次に押したときの動きを決める。 */
export function stepStatus(events: RunEvent[], step: StepType): StepStatus {
  const mine = events.filter((e) => e.step_type === step).sort((a, b) => a.seq - b.seq);
  const open = mine.find((e) => !e.end_at) ?? null;
  const last = mine.length ? mine[mine.length - 1] : null;
  const nextSeq = (last?.seq ?? 0) + 1;
  const state: StepState = open ? "doing" : last ? "done" : "todo";

  let timeText = "";
  if (open) timeText = `${formatHM(open.start_at)} 〜`;
  else if (last?.end_at) timeText = `${formatHM(last.start_at)} 〜 ${formatHM(last.end_at)}`;

  const seqForLabel = open ? open.seq : nextSeq;
  const label = step === "production" ? `生産 ${seqForLabel}回目` : STEP_LABELS[step];
  const action = open ? "end" : "start";
  return {
    step, state, label, timeText, open, nextSeq, action,
    needsQty: step === "production" && action === "end",
    needsReason: step === "production" && action === "start" && nextSeq >= 2,
    needsConfirm: step === "cleanup" && action === "end",
  };
}

/** 進捗率などの割合を「50%」の形にする。空なら「—」。 */
export function formatPercent(ratio: number | null | undefined): string {
  return ratio === null || ratio === undefined ? "—" : `${Math.round(ratio * 100)}%`;
}
