// 生産記録票の1つの面(1回目 / 2回目)。ライン欄の段と、作業の明細、トラブル欄。原紙に寄せた点: docs/design/production-record.md
import { boxCapacity, type Density, type Face, faceRows, firstArticleLines, GRID_ROWS, type RowSpec, timeRange } from "./recordLayout";
import { Bi, Head } from "./RecordBi";
import { fill, RECORD_TEXT, TIME_RANGE_SEPARATOR } from "./recordTexts";

const LINE_WIDTHS = { side1: [10, 12, 14, 21, 21, 22], side2: [10, 12, 14, 21, 43] }; // ライン欄の段(1回目は基板番号の欄がある)
const DETAIL_WIDTHS = [16, 27, 13, 3, 15, 10, 3, 13]; // 作業 / 作業者名 / 開始 / ～ / 終了 / 生産台数 / 初品確認の番号 / 記入欄

export function FaceTable({ face, side, density }: { face: Face | null; side: "side1" | "side2"; density: Density }) {
  return (
    <div className={`rec-face rec-${side}`} aria-label={RECORD_TEXT[side].ja}>
      <LineSection face={face} side={side} />
      <table className="rec-table rec-detail">
        <colgroup>{DETAIL_WIDTHS.map((w, i) => <col key={i} style={{ width: `${w}%` }} />)}</colgroup>
        <tbody>
          <tr className="rec-colhead rec-h-col">
            <td><Head k="work" /></td><td><Head k="worker" /></td>
            <td><Head k="startTime" /></td><td>{TIME_RANGE_SEPARATOR}</td><td><Head k="endTime" /></td>
            <td colSpan={3} />
          </tr>
          {faceRows(face).map((r, i) => <DetailRow key={i} row={r} face={face} density={density} />)}
          <tr><td colSpan={8} className="rec-left rec-colhead rec-trouble-head"><Bi k="trouble" inline /></td></tr>
          <tr>
            <td colSpan={8} className="rec-left rec-trouble-box">
              {face?.troubles.map((t, i) => <div key={i}>{t.name} {timeRange(t.start, t.end)}</div>)}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

/** ライン欄の段: 「1回目」「2回目」の右に、ラインの記号の枠(印を押す場所)、見出し「ライン」、手で書く欄(半田、ボンド、1回目だけ基板番号)。 */
function LineSection({ face, side }: { face: Face | null; side: "side1" | "side2" }) {
  const first = side === "side1";
  return (
    <table className="rec-table rec-linesec">
      <colgroup>{LINE_WIDTHS[side].map((w, i) => <col key={i} style={{ width: `${w}%` }} />)}</colgroup>
      <tbody>
        <tr className="rec-h-a">
          <td rowSpan={2} className="rec-large">{RECORD_TEXT[side].ja}</td>
          <td rowSpan={2} className="rec-linebox">
            <div className="rec-linesym">{face?.line_code ?? ""}</div>
            {face && <div className="rec-kno">{face.kitting_no}{!face.completed && <b> {RECORD_TEXT.notCompleted.ja}</b>}</div>}
          </td>
          <td rowSpan={2}><Bi k="line" /></td>
          <td><Bi k="solderLot" /></td>
          <td><Bi k="bondLot" /></td>
          {first && <td><Bi k="boardNo" /></td>}
        </tr>
        <tr className="rec-h-b"><td />{first ? <><td /><td /></> : <td />}</tr>
      </tbody>
    </table>
  );
}

function DetailRow({ row, face, density }: { row: RowSpec; face: Face | null; density: Density }) {
  const rec = row.rec;
  const qty = row.key === "production" ? <td className="rec-good">{rec?.good_qty ?? ""}</td> : <td className="rec-gray" />;
  return (
    <tr className="rec-row">
      <td><Bi k={row.label} /></td>
      <td>{rec ? `${rec.date} ${rec.worker}` : ""}</td>
      <td>{rec?.start ?? ""}</td><td>{TIME_RANGE_SEPARATOR}</td><td>{rec?.end ?? ""}</td>
      {row.right === "blank" && <td colSpan={3} />}
      {row.right === "labels" && (
        <>
          <td className="rec-bold rec-right-label rec-fs9"><Bi k="goodTotal" /></td>
          <td colSpan={2} className="rec-bold rec-right-label rec-fs85"><Bi k="firstArticle" /></td>
        </>
      )}
      {row.right === "grid" && (
        <>
          {qty}
          <td className="rec-n">{row.gridIndex + 1}</td>
          {row.gridIndex === 0 && <td rowSpan={GRID_ROWS} className="rec-box"><FirstArticleBox face={face} density={density} /></td>}
        </>
      )}
      {row.right === "tail" && (row.key === "production" ? <>{qty}<td colSpan={2} className="rec-gray" /></> : <td colSpan={3} className="rec-gray" />)}
    </tr>
  );
}

/** 初品確認の記入欄。日付(M/D)と作業者名を記録の順に1件1行。記録が無ければ空欄(手書き用)。 */
function FirstArticleBox({ face, density }: { face: Face | null; density: Density }) {
  const { lines, more } = firstArticleLines(face, boxCapacity(density));
  return (
    <>
      {lines.map((l, i) => <div key={i} className="rec-box-line">{l}</div>)}
      {more > 0 && <div className="rec-box-line rec-more">{fill(RECORD_TEXT.firstArticleMore.ja, { count: more })}</div>}
    </>
  );
}
