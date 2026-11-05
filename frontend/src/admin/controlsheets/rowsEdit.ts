// 管理画面「管理表の内容」の工程の行の編集(React に依存しない): 追加、削除、並べ替え、変更、入力の確認。詳細: docs/design/control-sheet.md
import type { components } from "../../api/schema";

export type Row = components["schemas"]["ControlRow"];
export type Kind = Row["kind"];
export type Link = Row["link"];

export const KINDS: Kind[] = ["none", "internal", "external"];
export const LINKS: Link[] = ["none", "run1", "run2", "xray"];

export const blankRow = (): Row => ({ name: "", name_vi: null, kind: "none", procedure: "", use_line: true, link: "none" });

/** index の次に空の行を足す(index が無ければ最後)。 */
export function addRow(rows: Row[], index?: number): Row[] {
  const at = index === undefined ? rows.length : index + 1;
  return [...rows.slice(0, at), blankRow(), ...rows.slice(at)];
}

export function removeRow(rows: Row[], index: number): Row[] {
  return rows.filter((_, i) => i !== index);
}

/** 行を1つ上(-1)か下(1)へ動かす。端のときはそのまま。 */
export function moveRow(rows: Row[], index: number, dir: -1 | 1): Row[] {
  const to = index + dir;
  if (to < 0 || to >= rows.length) return rows;
  const next = [...rows];
  [next[index], next[to]] = [next[to], next[index]];
  return next;
}

export function updateRow(rows: Row[], index: number, patch: Partial<Row>): Row[] {
  return rows.map((r, i) => (i === index ? { ...r, ...patch } : r));
}

/** 工程名が空の最初の行の番号(1から)。すべて入っていれば null。 */
export function firstBlankName(rows: Row[]): number | null {
  const i = rows.findIndex((r) => r.name.trim() === "");
  return i < 0 ? null : i + 1;
}

/** 保存のとき送る形(工程名の前後の空白と、空のベトナム語を整える)。 */
export function toPayload(rows: Row[]): Row[] {
  return rows.map((r) => ({ ...r, name: r.name.trim(), name_vi: r.name_vi?.trim() ? r.name_vi.trim() : null }));
}
