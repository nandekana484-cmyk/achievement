// 生産記録票(A4縦、日本語とベトナム語の併記)の上半分(承認欄、ロット)。各面の表は RecordFace.tsx。原紙に寄せた点: docs/design/production-record.md
// 様式: docs/design/forms/production-record-ver02.html。文言は recordTexts.ts、行の組み立ては recordLayout.ts。
import { type Density, type Lot, lotRowCount, quantityView, type Sheet } from "./recordLayout";
import { FaceTable } from "./RecordFace";
import { RECORD_TEXT } from "./recordTexts";

export function RecordSheet({ sheet, density }: { sheet: Sheet; density: Density }) {
  const h = sheet.header;
  const blanks = Array.from({ length: Math.max(0, lotRowCount(sheet) - sheet.lots.length) });
  return (
    <article className={`record-sheet record-${density}`} aria-label={RECORD_TEXT.title.ja}>
      <table className="rec-table rec-header">
        <colgroup><col style={{ width: "8%" }} /><col style={{ width: "8%" }} /><col style={{ width: "8%" }} /><col style={{ width: "50%" }} /><col style={{ width: "13%" }} /><col style={{ width: "13%" }} /></colgroup>
        <tbody>
          <tr>
            <td className="rec-small">{RECORD_TEXT.approver.ja}</td><td className="rec-small">{RECORD_TEXT.checker.ja}</td><td className="rec-small">{RECORD_TEXT.author.ja}</td>
            <td rowSpan={2}><div className="rec-title">{RECORD_TEXT.title.ja}</div><div className="rec-title-sub">{RECORD_TEXT.title.vi}</div></td>
            <td rowSpan={2} className="rec-bold">{RECORD_TEXT.processCheck.ja}</td><td rowSpan={2} />
          </tr>
          <tr className="rec-names"><td>{h.approver}</td><td>{h.checker}</td><td>{h.author}</td></tr>
          <tr>
            <td colSpan={4} className="rec-noborder" />
            <td colSpan={2} className="rec-noborder rec-revision">{RECORD_TEXT.revision.ja} {h.revision_date} &nbsp; {RECORD_TEXT.version.ja}{h.version}</td>
          </tr>
        </tbody>
      </table>

      <table className="rec-table rec-lots">
        <colgroup><col style={{ width: "12%" }} /><col style={{ width: "38%" }} /><col style={{ width: "25%" }} /><col style={{ width: "25%" }} /></colgroup>
        <tbody>
          <tr className="rec-colhead"><td>{RECORD_TEXT.fileNo.ja}</td><td>{RECORD_TEXT.productName.ja}</td><td>{RECORD_TEXT.lotNo.ja}</td><td>{RECORD_TEXT.quantity.ja}</td></tr>
          {sheet.lots.map((lot) => (
            <tr key={lot.lot_no} className="rec-lot">
              <td>{sheet.file_no}</td><td>{sheet.product_name}</td><td>{lot.lot_no}</td>
              <td><Quantity lot={lot} /></td>
            </tr>
          ))}
          {blanks.map((_, i) => <tr key={`blank-${i}`} className="rec-lot"><td /><td /><td /><td>&nbsp;/&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;/</td></tr>)}
        </tbody>
      </table>

      <FaceTable face={sheet.side1} side="side1" density={density} />
      <FaceTable face={sheet.side2} side="side2" density={density} />
    </article>
  );
}

/** 数量「A / B / C」。A の面が完了していて実績が A と違うときは、A と B に取消線を引き、すぐ右に実績と「B - A + 実績」を太字で出す(色は使わない)。 */
function Quantity({ lot }: { lot: Lot }) {
  const q = quantityView(lot);
  const show = (old: number | null, now: number | null) =>
    now == null ? <>{old ?? "-"}</> : <><s className="rec-a-old">{old ?? "-"}</s> <b className="rec-a-actual">{now}</b></>;
  return <>{show(q.a, q.actual)} / {q.newB == null ? (q.b ?? "-") : show(q.b, q.newB)} / {q.c ?? "-"}</>;
}
