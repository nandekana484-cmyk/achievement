// 識別票 2: バーコード印字 完了(A6横)、識別票 3: 1回目完了済み(A6横)。ロットごとに1枚。
// 様式: docs/design/forms/id-2-barcode-printed.html、id-3-side1-done.html(作りは同じで、表題と File № 欄の幅だけ違う)。
// 様式の2は見出しだけで値の欄が空だったので、3と同じく値を大きく出す。A6 から余白 3mm を除いた大きさに、比率を保って縮めて描く。
import { Barcode } from "./Barcode";
import { barSize } from "./code39";
import type { IdSlip } from "./idSlipLogic";
import { Bi, Fit, Shared, SLIP_SCALE } from "./SlipParts";

const INNER_MM = 146.7; // カードの幅(148mm - 外枠)
const PAD_X_MM = 3.2; // 左右の余白 6px ずつ + 外枠の分

export function Slip23({ kind, slip, lotNo }: { kind: 2 | 3; slip: IdSlip; lotNo: string }) {
  const filePct = kind === 2 ? 20 : 22;
  const suf = barSize(slip.suf, 100 * SLIP_SCALE, 0.4);
  return (
    <div className={`slip23 slip23-${kind}`}>
      <table className="slip-table">
        <tbody>
          <tr className="slip23-top">
            <td className="slip23-fileno" style={{ width: `${filePct}%` }}>
              <span className="slip23-label"><Shared k="fileNo" /></span>
              <div className="slip23-value"><Fit text={slip.file_no} widthMm={(filePct / 100) * INNER_MM - PAD_X_MM} heightMm={28} maxPx={26} maxLines={1} /></div>
            </td>
            <td className="slip23-product">
              <span className="slip23-label"><Shared k="productName" /></span>
              <div className="slip23-value"><Fit text={slip.product_name} widthMm={((100 - filePct) / 100) * INNER_MM - PAD_X_MM} heightMm={28} maxPx={26} maxLines={3} /></div>
            </td>
          </tr>
        </tbody>
      </table>
      <table className="slip-table">
        <tbody>
          <tr className="slip23-lot">
            <td>
              <span className="slip23-label"><Shared k="lotNo" /></span>
              <div className="slip23-value"><Fit text={lotNo} widthMm={INNER_MM - PAD_X_MM} heightMm={17} maxPx={26} maxLines={2} /></div>
            </td>
          </tr>
        </tbody>
      </table>
      <div className="slip23-bottom">
        <div className="slip23-title-ja">{kind === 2 ? <Bi k="title2" /> : <Bi k="title3" />}</div>
        <Barcode value={slip.suf} barMm={suf.barMm} heightMm={9} scale={SLIP_SCALE} label />
        <div className="slip23-format"><Bi k="format" /></div>
      </div>
    </div>
  );
}
