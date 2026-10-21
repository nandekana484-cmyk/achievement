// ラインの名前の表示。自動で付けた名前(「<記号>ライン」)のままなら選んだ言語の形で出し、人が変えた名前はそのまま出す。
import type { Translate } from "../i18n/translate";
import type { Line } from "./api";

export function lineName(line: Pick<Line, "line_code" | "name" | "auto_named">, t: Translate): string {
  return line.auto_named ? t("lineScreen.lineFallback", { code: line.line_code }) : line.name;
}
