// 生産記録票の様式の文言。日本語とベトナム語の併記で固定し、画面の言語の切り替えには従わない(紙の様式は1つ)。
// ja.ts / vi.ts / admin/messages.ts とは別に、ここにまとめる(コンポーネントに直接書かない)。詳細: docs/design/production-record.md
export type Bilingual = { ja: string; vi: string };

const b = (ja: string, vi: string): Bilingual => ({ ja, vi });

export const RECORD_TEXT = {
  title: b("実装工程 生産記録票", "PHIẾU GHI CHÉP SẢN XUẤT CÔNG ĐOẠN GẮN LINH KIỆN"),
  approver: b("承認", "Phê duyệt"),
  checker: b("確認", "Kiểm tra"),
  author: b("作成", "Lập phiếu"),
  revisionDate: b("改正日", "Ngày sửa đổi"),
  version: b("Ver.", "Ver."),
  processCheck: b("工程抜け確認印", "Dấu xác nhận không sót công đoạn"),
  fileNo: b("File №", "File №"),
  productName: b("製品名", "Tên sản phẩm"),
  lotNo: b("LOT No.", "LOT No."),
  quantity: b("数量", "Số lượng"),
  quantityNote: b("A:この計画の生産数 / B:これまでの累計 / C:ロットの発注数", "A: SL của kế hoạch này / B: Lũy kế / C: SL đặt hàng của lô"),
  solderLot: b("使用半田ロットNo", "Số lô hàn sử dụng"),
  bondLot: b("使用ボンドロットNo", "Số lô keo sử dụng"),
  boardNo: b("基板番号", "Số bo mạch"),
  side1: b("1回目", "LẦN 1"),
  side2: b("2回目", "LẦN 2"),
  line: b("ライン", "Line"),
  kittingNo: b("キッティングNo.", "Kitting No."),
  stepName: b("作業名", "Tên công việc"),
  worker: b("作業者名", "TÊN NGƯỜI THAO TÁC"),
  startTime: b("開始時間", "Giờ bắt đầu"),
  endTime: b("終了時間", "Giờ kết thúc"),
  setup: b("段取り", "Chuẩn bị"),
  n1Check: b("マスターチェック", "Kiểm tra master"),
  production: b("生産", "Sản xuất"),
  xray: b("X線検査", "Kiểm tra X-quang"),
  cleanup: b("片付け", "Dọn dẹp"),
  goodTotal: b("生産台数", "Số lượng sản xuất"),
  firstArticle: b("初品確認", "Kiểm tra sản phẩm đầu"),
  firstArticleMore: b("ほか {count} 件", "và {count} mục khác"),
  trouble: b("トラブル", "Sự cố"),
  troubleTime: b("時間", "Thời gian"),
  notPrintedYet: b("未完了", "Chưa hoàn thành"),
} as const;

/** 時間の範囲の区切り(トラブルの時間)。 */
export const TIME_RANGE_SEPARATOR = "〜";

export type RecordTextKey = keyof typeof RECORD_TEXT;

/** 差し込み({count})だけを置き換える。 */
export function fill(text: string, values: Record<string, string | number>): string {
  return text.replace(/\{(\w+)\}/g, (m, k: string) => (k in values ? String(values[k]) : m));
}
