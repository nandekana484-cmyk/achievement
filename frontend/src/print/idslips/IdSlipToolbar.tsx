// 識別票の印刷の操作バー(印刷に出ない所): 種類のチェック、ロットの選択、枚数、種類ごとの印刷ボタン、警告。
import { Link } from "react-router-dom";
import { useI18n } from "../../i18n/I18nProvider";
import { backUrl, barcodeWarnings, clampCopies, type IdSlip, isLotKind, MAX_COPIES, pagesOf, type Selection, toggleKind, toggleLot } from "./idSlipLogic";
import { SLIP_KINDS, type SlipKind } from "./idSlipTexts";

type Props = { slip: IdSlip; sel: Selection; onChange: (sel: Selection) => void; onPrint: (kind: SlipKind) => void };

export function IdSlipToolbar({ slip, sel, onChange, onPrint }: Props) {
  const { t } = useI18n();
  const warnings = barcodeWarnings(slip, sel);
  const lotKindChecked = sel.kinds.some(isLotKind);
  const setCopies = (kind: SlipKind, value: string) => onChange({ ...sel, copies: { ...sel.copies, [kind]: clampCopies(Number(value)) } });
  return (
    <div className="idslip-toolbar">
      <div className="idslip-head">
        <Link to={backUrl(slip)} className="btn">{t("idslip.back")}</Link>
        <strong>{slip.kitting_no}</strong>
        <span>{slip.product_name}</span>
      </div>
      <p className="idslip-hint">{t("idslip.hint")}</p>
      <table className="idslip-kinds">
        <thead>
          <tr><th>{t("idslip.colKind")}</th><th>{t("idslip.colUnit")}</th><th>{t("idslip.colCopies")}</th><th>{t("idslip.colPages")}</th><th /></tr>
        </thead>
        <tbody>
          {SLIP_KINDS.map((kind) => {
            const checked = sel.kinds.includes(kind);
            const pages = checked ? pagesOf(kind, sel).length : 0;
            return (
              <tr key={kind} className={checked ? "" : "idslip-off"}>
                <td>
                  <label className="idslip-check">
                    <input type="checkbox" checked={checked} onChange={() => onChange({ ...sel, kinds: toggleKind(sel.kinds, kind) })} />
                    {t(`idslip.kind.${kind}`)}
                  </label>
                </td>
                <td>{isLotKind(kind) ? t("idslip.unitLot") : t("idslip.unitKitting")}</td>
                <td>
                  <input
                    type="number" min={1} max={MAX_COPIES} inputMode="numeric" className="idslip-copies" disabled={!checked}
                    aria-label={`${t("idslip.colCopies")} ${t(`idslip.kind.${kind}`)}`} value={sel.copies[kind]} onChange={(e) => setCopies(kind, e.target.value)}
                  />
                  {isLotKind(kind) && <span className="idslip-note"> {t("idslip.perLot")}</span>}
                </td>
                <td>{t("idslip.pages", { count: pages })}</td>
                <td>
                  <button type="button" className="btn btn-primary" disabled={!checked || pages === 0} onClick={() => onPrint(kind)}>{t("idslip.print")}</button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {lotKindChecked && (
        <fieldset className="idslip-lots">
          <legend>{t("idslip.lots")}</legend>
          {slip.lots.map((l) => (
            <label key={l.lot_no} className="idslip-check">
              <input type="checkbox" checked={sel.lots.includes(l.lot_no)} onChange={() => onChange({ ...sel, lots: toggleLot(slip.lots.map((x) => x.lot_no), sel.lots, l.lot_no) })} />
              {l.lot_no}
            </label>
          ))}
          <button type="button" className="btn btn-small" onClick={() => onChange({ ...sel, lots: slip.lots.map((l) => l.lot_no) })}>{t("idslip.lotsAll")}</button>
          {sel.lots.length === 0 && <span className="idslip-warn">{t("idslip.noLots")}</span>}
        </fieldset>
      )}
      {warnings.map((w) => (
        <p key={`${w.field}:${w.value}`} className="idslip-warn" role="alert">{t("idslip.warn", { item: t(`idslip.item.${w.field}`), value: w.value })}</p>
      ))}
    </div>
  );
}
