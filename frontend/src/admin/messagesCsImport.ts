// 管理画面「管理表の内容」の Excel 取り込みの文言(日本語だけ)。詳細: docs/design/control-sheet.md
import { format, type Params } from "../i18n/translate";

const text = {
  "ci.title": "Excelから取り込む",
  "ci.note": "ファイルNo.ごとに1シートのブック(.xls、.xlsx、.xlsm)を選ぶと、まず確かめるだけの結果を出します(まだ登録しません)。確かめたあと、登録するシートを選んで「登録」を押します。ブックはサーバーの中で読むだけで、残しません。",
  "ci.choose": "ブックを選ぶ",
  "ci.reading": "「{name}」を読んでいます…",
  "ci.result": "「{name}」の確かめる結果(まだ登録していません)",
  "ci.counts": "新規 {new}・変更あり {changed}・変更なし {unchanged}・飛ばした {skipped}・エラー {error}",
  "ci.col.pick": "登録",
  "ci.col.sheet": "シート名",
  "ci.col.fileNo": "ファイルNo.",
  "ci.col.status": "状態",
  "ci.col.reason": "理由・違い",
  "ci.col.rows": "行の数",
  "ci.col.manager": "管理No",
  "ci.status.new": "新規",
  "ci.status.changed": "変更あり",
  "ci.status.unchanged": "変更なし",
  "ci.status.skipped": "飛ばした",
  "ci.status.error": "エラー",
  "ci.overwrite": "管理画面で直した内容を上書きします",
  "ci.overwriteTotal": "選んだシートのうち {count} 件は、管理画面で作った・直した内容を上書きします。上書きの前の内容は、各ファイルNo.の履歴から見られ、戻せます。",
  "ci.showChanges": "今の内容との違い({count} 件)",
  "ci.changesMore": "ほか {count} 件",
  "ci.showCarry": "ベトナム語と対応の引き継ぎ",
  "ci.carried": "引き継いだ行 {count} 件",
  "ci.lostCount": "引き継げずに消える {count} 件",
  "ci.lost": "{row} 行目「{name}」(工程名が変わった・なくなった)のベトナム語「{vi}」と対応「{link}」は消えます",
  "ci.link.none": "なし",
  "ci.link.run1": "1回目",
  "ci.link.run2": "2回目",
  "ci.link.xray": "X線検査",
  "ci.carrySummary": "工程名のベトナム語と対応を、今の内容の同じ工程名の行から引き継ぎます(引き継ぐ行 {carried} 件)。引き継げずに消えるものは {lost} 件です(各シートの違いを開くと見られます)。",
  "ci.field.manager_no": "管理No",
  "ci.field.row_count": "行の数",
  "ci.field.name": "{row} 行目の工程名",
  "ci.field.procedure": "{row} 行目の作業要領",
  "ci.field.kind": "{row} 行目の区分",
  "ci.field.use_line": "{row} 行目のライン名の欄",
  "ci.change": "{label}: 「{before}」→「{after}」",
  "ci.selectAll": "新規と変更ありをすべて選ぶ",
  "ci.selectNone": "すべて外す",
  "ci.apply": "登録({count} 件)",
  "ci.cancel": "やめる",
  "ci.nothingToRegister": "登録できるシートがありません",
  "ci.done": "{count} 件を登録しました(ブック「{name}」)",
  "ci.history": "取り込みの履歴",
  "ci.history.empty": "取り込みはまだありません",
  "ci.history.col.at": "日時",
  "ci.history.col.by": "取り込んだ人",
  "ci.history.col.book": "ブック名",
  "ci.history.col.sheets": "シート",
  "ci.history.col.count": "登録",
  "ci.badBook": "ブックを選んでください(.xls、.xlsx、.xlsm)",
} as const;

export type ImportKey = keyof typeof text;

/** Excel 取り込みの文言。 */
export function ci(key: ImportKey, params?: Params): string {
  return format(text[key], params);
}
