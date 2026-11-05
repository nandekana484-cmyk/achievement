// 管理画面「管理表の内容」の Excel 取り込みの決まり(React に依存しない): 登録するシートの初期値と選び方、送る本文の作り方、件数。詳細: docs/design/control-sheet.md
import type { components } from "../../api/schema";

export type ImportSheet = components["schemas"]["ImportSheetOut"];
export type ImportPreview = components["schemas"]["ImportPreviewOut"];
export type Status = ImportSheet["status"];

/** 登録できる状態(新規と変更あり)。ほかは登録の対象にならない。 */
export const REGISTERABLE: Status[] = ["new", "changed"];

export const isRegisterable = (s: ImportSheet): boolean => REGISTERABLE.includes(s.status) && s.file_no !== null;

/** 登録するシートの初期値(新規と変更あり)。ファイルNo.で持つ。 */
export function defaultSelection(sheets: ImportSheet[]): string[] {
  return sheets.filter(isRegisterable).map((s) => s.file_no as string);
}

/** 選び直す(登録できるシートだけ。順は一覧のまま)。 */
export function toggle(sheets: ImportSheet[], selected: string[], fileNo: string): string[] {
  return sheets.filter(isRegisterable).map((s) => s.file_no as string).filter((f) => (f === fileNo ? !selected.includes(f) : selected.includes(f)));
}

/** 選んだシートのうち、管理画面で作った・直した内容を上書きするものの数(確かめる画面に警告を出す)。 */
export function overwriteCount(sheets: ImportSheet[], selected: string[]): number {
  return sheets.filter((s) => s.overwrites_manual && s.file_no !== null && selected.includes(s.file_no)).length;
}

/** 登録の本文: 先頭の 10 桁(JSON の長さ)、選んだファイルNo.の JSON、ブック。サーバー(api/admin_control_sheet_import.py)の split_apply_body と同じ形。 */
export function applyBody(fileNos: string[], book: Blob): Blob {
  const json = new TextEncoder().encode(JSON.stringify({ file_nos: fileNos }));
  return new Blob([String(json.length).padStart(10, "0"), json, book]);
}

/** 受け付けるブックの拡張子。 */
export const BOOK_ACCEPT = ".xls,.xlsx,.xlsm";
