// 作業者の表示。同じ名前の人がいても区別できるよう、名前の横に作業者IDを出す。
import type { Operator } from "../../shared/api";

/** 「山田(Y001)」。作業者IDが無ければ名前だけ。 */
export function operatorLabel(name: string, workerId: string | null | undefined): string {
  return workerId ? `${name}(${workerId})` : name;
}

/** 名前順、同じ名前は作業者IDの順。 */
export function sortOperators(operators: Operator[]): Operator[] {
  return [...operators].sort((a, b) => a.name.localeCompare(b.name, "ja") || (a.worker_id ?? "").localeCompare(b.worker_id ?? ""));
}
