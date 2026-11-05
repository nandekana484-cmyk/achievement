// 識別票の5つ目: K社製品ロット管理票(A4縦。ロットごとに1枚)。様式: docs/design/forms/control-sheet-k.html。欄と元データ: docs/design/control-sheet.md
// 工程の行はファイルNo.ごとの内容(管理画面で登録)。1ページに収まるまで、描いてから測って、行の高さを先に、文字をあとから縮める(最小 8px)。
// 内容が変わったら、呼ぶ側が key を変えて作り直す(詰め具合を 0 からやり直すため)。
import { type RefObject, useLayoutEffect, useRef, useState } from "react";
import { type SheetRow, lotCounts, nextLevel, sheetRows } from "./controlSheetLayout";
import { SHEET_TEXT, type SheetTextKey } from "./controlSheetTexts";
import type { IdSlip } from "./idSlipLogic";
import { Fit } from "./SlipParts";

/** 日本語の下に、ベトナム語を小さい字で付ける。 */
function Bi({ k, vi = true }: { k: SheetTextKey; vi?: boolean }) {
  const { ja, vi: v } = SHEET_TEXT[k];
  return <>{ja}{vi && v && <span className="sk-vi">{v}</span>}</>;
}

const COLS = [4, 11, 33, 10, 12, 9, 7, 14];
const HEADS: SheetTextKey[] = ["no", "processName", "procedure", "lineName", "worker", "passQty", "ngQty", "ngReason"];

function ProcessCell({ row }: { row: SheetRow }) {
  const kind = row.kind === "none" ? null : SHEET_TEXT[row.kind];
  return (
    <td className="sk-name">
      {row.name && <b>{row.name}</b>}
      {row.nameVi && <span className="sk-vi">{row.nameVi}</span>}
      {kind && <span className="sk-kind">{kind.ja}<span className="sk-vi-inline"> {kind.vi}</span></span>}
    </td>
  );
}

function Rows({ rows }: { rows: SheetRow[] }) {
  return (
    <>
      {rows.map((r) => (
        <tr key={r.no} className="sk-row" data-row={r.no}>
          <td>{r.no}</td>
          <ProcessCell row={r} />
          <td className="sk-proc sk-lined">{r.procedure}</td>
          <td className={r.useLine ? "" : "sk-diagonal"} />
          <td /><td /><td /><td />
        </tr>
      ))}
      <tr className="sk-last">
        <td /><td />
        <td className="sk-to-assembly"><b>{SHEET_TEXT.toAssembly.ja}</b><span className="sk-vi">{SHEET_TEXT.toAssembly.vi}</span></td>
        <td /><td /><td /><td /><td />
      </tr>
    </>
  );
}

function Hanko({ k }: { k: SheetTextKey }) {
  return <><tr><td className="sk-hanko-head"><Bi k={k} /></td></tr><tr><td className="sk-hanko-cell" /></tr></>;
}

function Top({ slip }: { slip: IdSlip }) {
  return (
    <>
      <table className="sk-header">
        <tbody><tr>
          <td className="sk-h-left">
            <table className="sk-group">
              <tbody>
                <tr><td colSpan={2} className="sk-group-top"><Bi k="group" /></td></tr>
                <tr><td className="sk-group-label"><Bi k="setupFileNo" /></td><td className="sk-fileno">{slip.file_no}</td></tr>
              </tbody>
            </table>
          </td>
          <td className="sk-h-title"><div className="sk-title">{SHEET_TEXT.title.ja}</div></td>
          <td className="sk-h-right">
            <div className="sk-managerno"><Bi k="managerNo" /></div>
            <div className="sk-manager-value">{slip.control_sheet.manager_no}</div>
            <div className="sk-mp">{SHEET_TEXT.mp.ja}</div>
          </td>
        </tr></tbody>
      </table>
      <table className="sk-product">
        <tbody><tr><td>
          <div className="sk-product-in">
            <span className="sk-product-label"><Bi k="productName" /></span>
            <span className="sk-product-value"><Fit text={slip.product_name} widthMm={140} heightMm={9} maxPx={20} maxLines={2} className="sk-fit-left" /></span>
          </div>
        </td></tr></tbody>
      </table>
    </>
  );
}

function LotBlock({ slip, lotNo }: { slip: IdSlip; lotNo: string }) {
  const { a, c } = lotCounts(slip, lotNo);
  return (
    <table className="sk-lot">
      <colgroup><col style={{ width: "50%" }} /><col style={{ width: "25%" }} /><col style={{ width: "25%" }} /></colgroup>
      <tbody>
        <tr className="sk-lot-row">
          <td className="sk-lot-left">
            <div className="sk-lot-line">
              <span className="sk-lot-label"><Bi k="lotNo" /></span>
              <div className="sk-lot-box">
                <div className="sk-lot-main"><Fit text={lotNo} widthMm={49} heightMm={7.4} maxPx={18} maxLines={1} /></div>
                <div className="sk-lot-small" />
              </div>
            </div>
            <div className="sk-final-arrow"><span>{SHEET_TEXT.arrow.ja}</span><span className="sk-final-bar" /><span><Bi k="finalMark" /></span></div>
          </td>
          <td className="sk-qty-label"><Bi k="lotQty" /></td>
          <td className="sk-qty-value">
            <span className="sk-qty-line"><b className="sk-a">{a}</b><span className="sk-slash">{SHEET_TEXT.slash.ja}</span><b className="sk-c">{c}</b></span>
            <span className="sk-qty-total"><Bi k="lotTotal" /></span>
          </td>
        </tr>
        <tr className="sk-circle-row">
          <td />
          <td colSpan={2}><div className="sk-final-circle" /></td>
        </tr>
      </tbody>
    </table>
  );
}

function Bottom() {
  return (
    <>
      <table className="sk-bottom">
        <tbody><tr>
          <td className="sk-b-left">
            <div className="sk-skip-wrap">
              <table className="sk-skip">
                <tbody><tr><td className="sk-skip-head"><Bi k="skipStamp" /></td></tr><tr><td className="sk-skip-cell" /></tr></tbody>
              </table>
            </div>
            <div className="sk-memo-title"><Bi k="memo" /></div>
            <div className="sk-memo-box sk-lined" />
          </td>
          <td className="sk-b-right">
            <table className="sk-hanko"><tbody><Hanko k="made" /><Hanko k="checked" /><Hanko k="approved" /></tbody></table>
          </td>
        </tr></tbody>
      </table>
      <div className="sk-white">{SHEET_TEXT.whitePaper.ja}</div>
    </>
  );
}

function Sheet({ slip, lotNo, level, inner }: { slip: IdSlip; lotNo: string; level: number; inner: RefObject<HTMLDivElement> }) {
  return (
    <div className={`sk sk-d${level}`} data-level={level}>
      <div ref={inner} className="sk-inner">
        <Top slip={slip} />
        <LotBlock slip={slip} lotNo={lotNo} />
        <div className="sk-progress-title"><Bi k="progressTitle" /></div>
        <table className="sk-main">
          <colgroup>{COLS.map((w, i) => <col key={i} style={{ width: `${w}%` }} />)}</colgroup>
          <tbody>
            <tr className="sk-head-row">{HEADS.map((k) => <td key={k}><Bi k={k} /></td>)}</tr>
            <Rows rows={sheetRows(slip.control_sheet)} />
          </tbody>
        </table>
        <Bottom />
      </div>
    </div>
  );
}

export function ControlSheet({ slip, lotNo }: { slip: IdSlip; lotNo: string }) {
  const inner = useRef<HTMLDivElement>(null);
  const [level, setLevel] = useState(0);
  useLayoutEffect(() => {
    const next = nextLevel(level, inner.current?.getBoundingClientRect().height ?? 0);
    if (next !== null) setLevel(next);
  }, [level, slip, lotNo]);
  return <Sheet slip={slip} lotNo={lotNo} level={level} inner={inner} />;
}
