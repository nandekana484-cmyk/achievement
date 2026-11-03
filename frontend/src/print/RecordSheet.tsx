// 生産記録票(A4縦、日本語とベトナム語の併記)。様式: docs/design/forms/production-record-ver02.html
// 文言は recordTexts.ts、行の組み立ては recordLayout.ts。行を足す所(ロット、生産、同じ工程の複数の記録)だけ、同じ見た目で増やす。
import { type Density, type Face, firstArticleCells, faceRows, lotRowCount, type RowSpec, type Sheet, timeRange } from "./recordLayout";
import { fill, RECORD_TEXT, type RecordTextKey, TIME_RANGE_SEPARATOR } from "./recordTexts";

/** 日本語の下に、ベトナム語を小さい字で付ける(様式の sub-text)。inline なら同じ行に続ける。 */
function Bi({ k, inline }: { k: RecordTextKey; inline?: boolean }) {
  const { ja, vi } = RECORD_TEXT[k];
  if (!vi) return <>{ja}</>;
  return <>{ja}{inline ? <span className="rec-sub-inline"> {vi}</span> : <span className="rec-sub">{vi}</span>}</>;
}

/** 「作業 / CÔNG VIỆC」の形(明細の見出し)。 */
function Head({ k }: { k: RecordTextKey }) {
  const { ja, vi } = RECORD_TEXT[k];
  return <>{ja} / {vi}</>;
}

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
              <td>{[lot.produced, lot.cumulative, lot.ordered].map((q) => q ?? "-").join(" / ")}</td>
            </tr>
          ))}
          {blanks.map((_, i) => <tr key={`blank-${i}`} className="rec-lot"><td /><td /><td /><td>&nbsp;/&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;/</td></tr>)}
        </tbody>
      </table>

      <FaceTable face={sheet.side1} side="side1" />
      <FaceTable face={sheet.side2} side="side2" />
    </article>
  );
}

function FaceTable({ face, side }: { face: Face | null; side: "side1" | "side2" }) {
  const first = side === "side1";
  return (
    <table className={`rec-table rec-face rec-${side}`} aria-label={RECORD_TEXT[side].ja}>
      <colgroup>{[18, 27, 15, 3, 15, 11, 11].map((w, i) => <col key={i} style={{ width: `${w}%` }} />)}</colgroup>
      <tbody>
        <tr className="rec-h-a">
          <td rowSpan={2} className="rec-large">{RECORD_TEXT[side].ja}</td>
          <td><Bi k="line" /></td>
          <td colSpan={2}><Bi k="solderLot" /></td>
          {first ? <><td><Bi k="bondLot" /></td><td colSpan={2}><Bi k="boardNo" /></td></> : <td colSpan={3}><Bi k="bondLot" /></td>}
        </tr>
        <tr className="rec-h-b">
          <td>{face?.line_code ?? ""}{face && <span className="rec-kno"> {face.kitting_no}</span>}</td>
          <td colSpan={2} />
          {first ? <><td /><td colSpan={2} /></> : <td colSpan={3} />}
        </tr>
        <tr className="rec-colhead">
          <td><Head k="work" /></td>
          <td><Head k="worker" /></td>
          <td><Head k="startTime" /></td><td>{TIME_RANGE_SEPARATOR}</td><td><Head k="endTime" /></td>
          <td colSpan={2} className="rec-open">{face && !face.completed ? RECORD_TEXT.notCompleted.ja : ""}</td>
        </tr>
        {faceRows(face).map((r, i) => <DetailRow key={i} row={r} face={face} />)}
        <tr><td colSpan={7} className="rec-left rec-colhead rec-trouble-head"><Bi k="trouble" inline /></td></tr>
        <tr>
          <td colSpan={7} className="rec-left rec-trouble-box">
            {face?.troubles.map((t, i) => <div key={i}>{t.name} {timeRange(t.start, t.end)}</div>)}
          </td>
        </tr>
      </tbody>
    </table>
  );
}

function DetailRow({ row, face }: { row: RowSpec; face: Face | null }) {
  const first = firstArticleCells(face);
  const rec = row.rec;
  return (
    <tr className={`rec-r-${row.height}`}>
      <td className={row.height === "grid" ? "rec-label-inline" : undefined}><Bi k={row.label} inline={row.height === "grid"} /></td>
      <td>{rec ? `${rec.date} ${rec.worker}` : ""}</td>
      <td>{rec?.start ?? ""}</td><td>{TIME_RANGE_SEPARATOR}</td><td>{rec?.end ?? ""}</td>
      {row.right === "blank" && <td colSpan={2} />}
      {row.right === "gray" && <td colSpan={2} className="rec-gray" />}
      {row.right === "labels" && (
        <>
          <td className="rec-bold rec-right-label rec-fs9"><Bi k="goodTotal" /></td>
          <td className="rec-bold rec-right-label rec-fs85"><Bi k="firstArticle" /></td>
        </>
      )}
      {row.right === "grid" && (
        <>
          {row.gridIndex === 0 && <td rowSpan={4} className="rec-good">{face ? face.good_total : ""}</td>}
          <td className="rec-first">
            <span className="rec-n">{row.gridIndex + 1}</span> {first.cells[row.gridIndex]}
            {row.gridIndex === first.cells.length - 1 && first.more > 0 && <span className="rec-more"> {fill(RECORD_TEXT.firstArticleMore.ja, { count: first.more })}</span>}
          </td>
        </>
      )}
    </tr>
  );
}
