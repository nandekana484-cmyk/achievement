// 生産記録票の様式の文言。日本語とベトナム語の併記で固定し、画面の言語の切り替えには従わない(紙の様式は1つ)。
// 文言は様式(docs/design/forms/production-record-ver02.html)のとおり。ベトナム語が無い欄は vi を空にする。
// ja.ts / vi.ts / admin/messages.ts とは別に、ここにまとめる(コンポーネントに直接書かない)。詳細: docs/design/production-record.md
export type Bilingual = { ja: string; vi: string };

const b = (ja: string, vi = ""): Bilingual => ({ ja, vi });

export const RECORD_TEXT = {
  title: b("実装工程 生産記録票", "BIỂU GHI CHÉP SẢN XUẤT"),
  approver: b("承認"),
  checker: b("確認"),
  author: b("作成"),
  processCheck: b("工程抜け確認印"),
  revision: b("改正"),
  version: b("Ver."),
  fileNo: b("File №"),
  productName: b("製品名"),
  lotNo: b("LOT No."),
  quantity: b("数量"),
  side1: b("1回目"),
  side2: b("2回目"),
  line: b("ライン", "ĐÓNG DẤU CHUYỀN"),
  solderLot: b("使用半田ロットNo", "SỐ LÔ HÀN"),
  bondLot: b("使用ボンドロットNo", "SỐ LÔ KEO"),
  boardNo: b("基板番号 / N° DA PLACA", "MÃ SỐ BO MẠCH"),
  work: b("作業", "CÔNG VIỆC"),
  worker: b("作業者名", "TÊN NGƯỜI THAO TÁC"),
  startTime: b("開始時間", "BẮT ĐẦU"),
  endTime: b("終了時間", "KẾT THÚC"),
  setup: b("段取り", "CHUẨN BỊ"),
  n1Check: b("マスターチェック", "KIỂM TRA MASTER"),
  production: b("生産", "SẢN XUẤT"),
  xray: b("X線検査", "KIỂM TRA X-RAY"),
  cleanup: b("片付け", "DỌN DẸP"),
  goodTotal: b("生産台数", "SẢN LƯỢNG"),
  firstArticle: b("初品確認", "XÁC NHẬN ĐẦU HÀNG"),
  firstArticleMore: b("ほか {count} 件"),
  trouble: b("トラブル", "SỰ CỐ / VẤN ĐỀ"),
  notCompleted: b("未完了"),
} as const;

export type RecordTextKey = keyof typeof RECORD_TEXT;

/** 時間の範囲の区切り(様式の「～」)。 */
export const TIME_RANGE_SEPARATOR = "～";

/** 差し込み({count})だけを置き換える。 */
export function fill(text: string, values: Record<string, string | number>): string {
  return text.replace(/\{(\w+)\}/g, (m, k: string) => (k in values ? String(values[k]) : m));
}
