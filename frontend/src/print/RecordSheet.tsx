// 生産記録票(A4縦、日本語とベトナム語の併記)。文言は recordTexts.ts、行の組み立ては recordLayout.ts。詳細: docs/design/production-record.md
import { Fragment } from "react";
import { type Density, type Face, firstArticleCells, stepGroups, type Sheet, timeRange, troubleCount } from "./recordLayout";
import { fill, RECORD_TEXT, type RecordTextKey } from "./recordTexts";

function Text({ k, className }: { k: RecordTextKey; className?: string }) {
  const text = RECORD_TEXT[k];
  return (
    <span className={`rec-text${className ? ` ${className}` : ""}`}>
      <span className="rec-ja">{text.ja}</span>
      <span className="rec-vi">{text.vi}</span>
    </span>
  );
}

export function RecordSheet({ sheet, density }: { sheet: Sheet; density: Density }) {
  const h = sheet.header;
  return (
    <article className={`record-sheet record-${density}`} aria-label={RECORD_TEXT.title.ja}>
      <header className="rec-head">
        <h1 className="rec-title"><Text k="title" /></h1>
        <table className="rec-sign">
          <tbody>
            <tr><th><Text k="approver" /></th><th><Text k="checker" /></th><th><Text k="author" /></th><th><Text k="processCheck" /></th></tr>
            <tr className="rec-sign-name"><td>{h.approver}</td><td>{h.checker}</td><td>{h.author}</td><td /></tr>
            <tr><th><Text k="revisionDate" /></th><td>{h.revision_date}</td><th><Text k="version" /></th><td>{h.version}</td></tr>
          </tbody>
        </table>
      </header>

      <table className="rec-lots">
        <thead>
          <tr>
            <th><Text k="fileNo" /></th><th><Text k="productName" /></th><th><Text k="lotNo" /></th>
            <th><Text k="quantity" /> <span className="rec-note">A / B / C</span></th>
          </tr>
        </thead>
        <tbody>
          {sheet.lots.map((lot) => (
            <tr key={lot.lot_no}>
              <td>{sheet.file_no}</td><td>{sheet.product_name}</td><td>{lot.lot_no}</td>
              <td className="rec-num">{[lot.produced, lot.cumulative, lot.ordered].map((q) => q ?? "-").join(" / ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="rec-note"><span>{RECORD_TEXT.quantityNote.ja}</span> <span>{RECORD_TEXT.quantityNote.vi}</span></p>

      <FaceBlock face={sheet.side1} side="side1" />
      <FaceBlock face={sheet.side2} side="side2" />
    </article>
  );
}

function FaceBlock({ face, side }: { face: Face | null; side: "side1" | "side2" }) {
  const first = firstArticleCells(face);
  return (
    <section className="rec-face" aria-label={RECORD_TEXT[side].ja}>
      <h2 className="rec-face-head">
        <Text k={side} />
        <span className="rec-face-line"><Text k="line" />: {face?.line_code ?? ""}</span>
        <span className="rec-face-kno">{face?.kitting_no ?? ""}</span>
        {face && !face.completed && <span className="rec-face-open"><Text k="notPrintedYet" /></span>}
      </h2>
      <table className="rec-materials">
        <tbody>
          <tr>
            <th><Text k="solderLot" /></th><td />
            <th><Text k="bondLot" /></th><td />
            {side === "side1" && <><th><Text k="boardNo" /></th><td /></>}
          </tr>
        </tbody>
      </table>
      <table className="rec-steps">
        <thead>
          <tr>
            <th className="rec-c-step"><Text k="stepName" /></th><th className="rec-c-worker"><Text k="worker" /></th>
            <th className="rec-c-time"><Text k="startTime" /></th><th className="rec-c-time"><Text k="endTime" /></th>
          </tr>
        </thead>
        <tbody>
          {stepGroups(face).map((g) => (
            <Fragment key={g.key}>
              {g.rows.map((r, i) => (
                <tr key={`${g.key}-${i}`}>
                  {i === 0 && <th rowSpan={g.rows.length} className="rec-step-name"><Text k={g.label} /></th>}
                  <td>{r ? `${r.date} ${r.worker}` : ""}</td><td className="rec-num">{r?.start ?? ""}</td><td className="rec-num">{r?.end ?? ""}</td>
                </tr>
              ))}
            </Fragment>
          ))}
        </tbody>
      </table>
      <table className="rec-foot">
        <tbody>
          <tr>
            <th><Text k="goodTotal" /></th><td className="rec-num">{face ? face.good_total : ""}</td>
            <th><Text k="firstArticle" /></th>
            {first.cells.map((c, i) => <td key={i}><span className="rec-n">{i + 1}</span> {c}{i === first.cells.length - 1 && first.more > 0 ? ` ${fill(RECORD_TEXT.firstArticleMore.ja, { count: first.more })}` : ""}</td>)}
          </tr>
        </tbody>
      </table>
      <table className="rec-trouble">
        <thead><tr><th><Text k="trouble" /></th><th className="rec-c-trouble-time"><Text k="troubleTime" /></th></tr></thead>
        <tbody>
          {Array.from({ length: troubleCount(face) }, (_, i) => face?.troubles[i]).map((x, i) => (
            <tr key={i}><td>{x?.name ?? ""}</td><td className="rec-num">{x ? timeRange(x.start, x.end) : ""}</td></tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
