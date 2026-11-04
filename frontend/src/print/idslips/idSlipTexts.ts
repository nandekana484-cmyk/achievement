// 識別票(4種類)の様式の文言。日本語とベトナム語の併記で固定し、画面の言語の切り替えには従わない(紙の様式は1つ)。
// 文言は様式(docs/design/forms/id-1〜id-4*.html)のとおり。ポルトガル語は外した。共通の見出し(★)は4種類で同じ。
// ベトナム語の訳は仮の初版(現場で確認する。一覧は docs/design/id-slips.md)。ja.ts / vi.ts とは別に、ここにまとめる。
import type { Bilingual } from "../recordTexts";

const b = (ja: string, vi = ""): Bilingual => ({ ja, vi });

export const SLIP_TEXT = {
  // ★ 4種類で同じ見出し
  fileNo: b("File №"),
  productName: b("製品名", "Tên sản phẩm"),
  lotNo: b("ロットNo.", "Số lô"),
  kittingNo: b("キッティングNo.", "Số danh sách kitting"),
  // 1 基板製品ロット現品票
  title1: b("基板製品ロット現品票", "Phiếu hàng lô sản phẩm bo mạch"),
  rohs: b("完全RoHS対応品"),
  quantity: b("数量", "Số lượng"),
  splitQty: b("分割数量", "Số lượng chia"),
  lotTotalQty: b("LOT総数", "Tổng số lượng LOT"),
  lotCount: b("LOT数", "Số LOT"),
  splitLotCount: b("分割LOT数", "LOT chia"),
  lotSplitTotal: b("LOT分割総数", "Tổng LOT chia"),
  splitTotal: b("分割総数", "Tổng số lần chia"),
  date: b("日付", "Ngày"),
  partsAfter: b("部品後付", "Gắn linh kiện bổ sung"),
  visual1: b("目視検査①", "Kiểm tra bằng mắt ①"),
  visual2: b("目視検査②", "Kiểm tra bằng mắt ②"),
  boardCut: b("基板カット", "Cắt bo mạch"),
  boardTest: b("基板電検", "Kiểm tra điện bo mạch"),
  memo: b("メモ", "Ghi chú"),
  scrap: b("スクラップ", "Phế phẩm"),
  checkerNg: b("チェッカーNG", "NG máy kiểm tra"),
  bond: b("ボンド", "Keo"),
  bondCheck: b("ボンド確認", "Xác nhận keo"),
  countCheck: b("枚数確認", "Xác nhận số tấm"),
  receiptCheck: b("受取確認", "Xác nhận nhận hàng"),
  paperColor: b("【用紙色：白色】", "Màu giấy: trắng"),
  // 2 バーコード印字 完了 / 3 1回目完了済み(表題は様式のまま)
  title2: b("バーコード印字 完了", "Hoàn tất in mã vạch"),
  title3: b("1回目完了済み", "Lần đầu tiên hoàn thành"),
  format: b("Format 2018/1/18"),
  // 4 バーコード照合用
  title4: b("バーコード照合用", "Đối chiếu mã vạch"),
} as const;

export type SlipTextKey = keyof typeof SLIP_TEXT;

/** 4種類の識別票の名前(操作バーの種類のチェックの横に出す名前は ja.ts / vi.ts)。 */
export const SLIP_KINDS = [1, 2, 3, 4] as const;
export type SlipKind = (typeof SLIP_KINDS)[number];
