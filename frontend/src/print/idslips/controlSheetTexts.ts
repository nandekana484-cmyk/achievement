// K社製品ロット管理票(識別票の5つ目)の様式の文言。日本語とベトナム語の併記で固定し、画面の言語の切り替えには従わない(紙の様式は1つ)。
// 様式は docs/design/forms/control-sheet-k.html。ポルトガル語は外し、日本語の下にベトナム語を小さい字で付けた。
// 表題「K社製品ロット管理票」・「MP」・「WHITE PAPER(A4)」は様式のまま(固定。ベトナム語なし)。ベトナム語の訳は仮の初版(一覧は docs/design/control-sheet.md)。
import type { Bilingual } from "../recordTexts";

const b = (ja: string, vi = ""): Bilingual => ({ ja, vi });

export const SHEET_TEXT = {
  title: b("K社製品ロット管理票"), // 固定(様式のまま。ベトナム語なし)
  mp: b("MP"),
  whitePaper: b("WHITE PAPER(A4)"),
  slash: b("／"),
  arrow: b("▲"),
  group: b("基板実装Gr.", "Nhóm lắp ráp bo mạch"),
  setupFileNo: b("セットアップファイルNo.", "Số tệp thiết lập"),
  managerNo: b("管理No", "Số quản lý"),
  productName: b("製品名", "Tên sản phẩm"),
  lotNo: b("ロットNo.：", "Số lô"),
  finalMark: b("分割最終記号", "Ký hiệu chia lần cuối"),
  lotQty: b("当ロット数", "Số lượng lô này"),
  lotTotal: b("ロット総数", "Tổng số lượng lô"),
  progressTitle: b("「作業進捗確認欄・作業要領記入欄」", "Bảng xác nhận tiến độ · ghi quy trình làm việc"),
  no: b("NO"),
  processName: b("工程名", "Tên công đoạn"),
  procedure: b("作業要領・注意点", "Quy trình làm việc · Điểm lưu ý"),
  lineName: b("ライン名", "Tên dây chuyền"),
  worker: b("作業者/日付", "Người làm/Ngày"),
  passQty: b("合格/完了数", "Số đạt/hoàn thành"),
  ngQty: b("NG数", "Số NG"),
  ngReason: b("NG理由", "Lý do NG"),
  internal: b("社内", "Nội bộ"),
  external: b("社外", "Bên ngoài"),
  toAssembly: b("・組立工程へ", "Chuyển sang công đoạn lắp ráp"),
  skipStamp: b("工程抜け確認印", "Dấu xác nhận không sót công đoạn"),
  memo: b("「メモ・処置欄」", "Ghi chú · Xử lý"),
  made: b("作　成", "Lập"),
  checked: b("確　認", "Xác nhận"),
  approved: b("承　認", "Phê duyệt"),
} as const;

export type SheetTextKey = keyof typeof SHEET_TEXT;
