// 識別票 1: 基板製品ロット現品票(A6縦)。ロットごとに1枚。様式: docs/design/forms/id-1-lot-slip.html
// 見た目は様式のまま(外枠は黒、ポルトガル語なし)。A6 から余白 3mm を除いた大きさに、比率を保って縮めて描く。
import { Barcode } from "./Barcode";
import { barSize, isCode39, modulesOf } from "./code39";
import type { IdSlip } from "./idSlipLogic";
import { Bi, Fit, Shared, SLIP_SCALE } from "./SlipParts";

const S = SLIP_SCALE;
const TABLE_MM = 95.9; // 表の幅(105mm - 左右の余白 4mm ずつ - 外枠)
const CELL_PAD_MM = 1.1; // 左右の余白 2px ずつ
const BAR_MAX_MM = 0.35;

/** 製品名・Lot.№ の欄のバーコードの枠(右の2列)の幅(%)。ロットNo.が長くて 0.25mm でも収まらないときは広げる。 */
export function barcodeColumnPercent(lotNo: string): number {
  const need = isCode39(lotNo) ? (modulesOf(lotNo) * 0.25) / S + CELL_PAD_MM : 0;
  return Math.max(40, Math.ceil((need / TABLE_MM) * 1000) / 10);
}

function Line({ label, value, barPct, bar }: { label: "productName" | "lotNo"; value: string; barPct: number; bar: string }) {
  const nameMm = ((100 - 20 - barPct) / 100) * TABLE_MM - CELL_PAD_MM;
  const avail = ((barPct / 100) * TABLE_MM - CELL_PAD_MM) * S;
  const size = barSize(bar, avail, BAR_MAX_MM);
  return (
    <tr className="slip1-h24">
      <td className="slip1-lbl"><Shared k={label} /></td>
      <td colSpan={2} className="slip1-val"><Fit text={value} widthMm={nameMm} heightMm={6.2} maxPx={14} maxLines={2} /></td>
      <td colSpan={2}><Barcode value={bar} barMm={size.barMm} heightMm={5} scale={S} /></td>
    </tr>
  );
}

export function Slip1({ slip, lotNo, orderQty }: { slip: IdSlip; lotNo: string; orderQty: number | null }) {
  const barPct = barcodeColumnPercent(lotNo);
  const rest = 100 - 20 - barPct;
  const widths = [20, (rest * 23) / 40, (rest * 17) / 40, barPct / 2, barPct / 2];
  const suf = barSize(slip.suf, 0.46 * TABLE_MM * S, 0.4);
  const sufPct = Math.max(46, Math.ceil(((suf.widthMm / S + 1) / TABLE_MM) * 1000) / 10);
  return (
    <div className="slip1">
      <div>
        <div className="slip1-titles">
          <div className="slip1-main"><Bi k="title1" /></div>
          <div className="slip1-rohs"><Bi k="rohs" /></div>
        </div>
        <table className="slip-table">
          <colgroup>{widths.map((w, i) => <col key={i} style={{ width: `${w}%` }} />)}</colgroup>
          <tbody>
            <Line label="productName" value={slip.product_name} barPct={barPct} bar={slip.file_no} />
            <Line label="lotNo" value={lotNo} barPct={barPct} bar={lotNo} />
            <tr className="slip1-h30">
              <td className="slip1-lbl"><Bi k="quantity" /></td>
              <td colSpan={4} className="slip1-split">
                <span className="slip1-note slip1-tl"><Bi k="splitQty" /></span>
                <span className="slip1-slash">/ <b className="slip1-qty">{orderQty ?? ""}</b></span>
                <span className="slip1-note slip1-br"><Bi k="lotTotalQty" /></span>
              </td>
            </tr>
            <tr className="slip1-h24">
              <td className="slip1-lbl"><Bi k="lotCount" /></td>
              <td colSpan={4} className="slip1-split">
                <span className="slip1-note slip1-tl"><Bi k="splitLotCount" /></span>
                <span className="slip1-slash">/</span>
                <span className="slip1-note slip1-br"><Bi k="lotSplitTotal" /></span>
              </td>
            </tr>
            <tr className="slip1-h16 slip1-small">
              <td rowSpan={4} className="slip1-lbl"><Bi k="splitTotal" /></td>
              <td><Bi k="date" /></td><td><Bi k="quantity" /></td><td><Bi k="date" /></td><td><Bi k="quantity" /></td>
            </tr>
            {[0, 1, 2].map((i) => <tr key={i} className="slip1-h18"><td /><td /><td /><td /></tr>)}
          </tbody>
        </table>
        <div className="slip1-double" />
        <table className="slip-table">
          <tbody>
            <tr className="slip1-h16 slip1-small">
              {(["partsAfter", "visual1", "visual2", "boardCut", "boardTest"] as const).map((k) => <td key={k} style={{ width: "20%" }}><Bi k={k} /></td>)}
            </tr>
            <tr className="slip1-h38"><td /><td /><td /><td /><td /></tr>
          </tbody>
        </table>
        <table className="slip-table slip1-memo-table">
          <colgroup>{[16, 18, 15, 16, 17, 18].map((w, i) => <col key={i} style={{ width: `${w}%` }} />)}</colgroup>
          <tbody>
            <tr><td colSpan={6} className="slip1-memo"><Bi k="memo" /></td></tr>
            <tr className="slip1-h44">
              {(["scrap", "checkerNg", "bond", "bondCheck", "countCheck"] as const).map((k) => <td key={k} className="slip1-stamp"><span className="slip1-stamp-title"><Bi k={k} /></span></td>)}
              <td className="slip1-stamp slip1-thick"><span className="slip1-stamp-title"><Bi k="receiptCheck" /></span></td>
            </tr>
          </tbody>
        </table>
      </div>
      <table className="slip1-bottom">
        <colgroup><col style={{ width: `${Math.max(12, 23 - (sufPct - 46))}%` }} /><col style={{ width: "14%" }} /><col style={{ width: "17%" }} /><col style={{ width: `${sufPct}%` }} /></colgroup>
        <tbody>
          <tr>
            <td className="slip1-paper"><Bi k="paperColor" /></td>
            <td className="slip1-fileno-label"><Shared k="fileNo" /></td>
            <td className="slip1-fileno">{slip.file_no}</td>
            <td className="slip1-sufcell"><Barcode value={slip.suf} barMm={suf.barMm} heightMm={6.3} scale={S} label /></td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
