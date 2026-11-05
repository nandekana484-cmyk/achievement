// 識別票(4種類)の印刷用のページ。計画を選んで開き、種類・ロットを選び、種類ごとの「この種類を印刷」で window.print を呼ぶ
// (その種類のページだけを印刷に出す。PDF の生成やサーバー側の印刷はしない)。詳細: docs/design/id-slips.md
import { useEffect, useState } from "react";
import { flushSync } from "react-dom";
import { useParams } from "react-router-dom";
import { useI18n } from "../../i18n/I18nProvider";
import { api } from "../../shared/api";
import { Notice } from "../../shared/Notice";
import { type IdSlip, initialSelection, pagesOf, type Selection } from "./idSlipLogic";
import { IdSlipToolbar } from "./IdSlipToolbar";
import type { SlipKind } from "./idSlipTexts";
import { ControlSheet } from "./ControlSheet";
import { Slip1 } from "./Slip1";
import { Slip23 } from "./Slip23";
import { Slip4 } from "./Slip4";

function Page({ kind, slip, lotNo }: { kind: SlipKind; slip: IdSlip; lotNo: string | null }) {
  const qty = slip.lots.find((l) => l.lot_no === lotNo)?.order_qty ?? null;
  const land = kind === 2 || kind === 3;
  return (
    <div className={`slip-frame ${kind === 5 ? "slip-frame-a4" : land ? "slip-frame-l" : "slip-frame-p"}`} data-kind={kind} data-lot={lotNo ?? ""}>
      {kind === 1 && lotNo !== null && <div className="slip-scale"><Slip1 slip={slip} lotNo={lotNo} orderQty={qty} /></div>}
      {land && lotNo !== null && <div className="slip-scale slip-scale-l"><Slip23 kind={kind as 2 | 3} slip={slip} lotNo={lotNo} /></div>}
      {kind === 4 && <Slip4 slip={slip} />}
      {kind === 5 && lotNo !== null && <ControlSheet key={`${lotNo}:${JSON.stringify(slip.control_sheet)}`} slip={slip} lotNo={lotNo} />}
    </div>
  );
}

export function IdSlipPage() {
  const { kittingNo = "" } = useParams();
  const { t } = useI18n();
  const [slip, setSlip] = useState<IdSlip | null>(null);
  const [sel, setSel] = useState<Selection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [printing, setPrinting] = useState<SlipKind | null>(null);

  useEffect(() => {
    let alive = true;
    api.GET("/api/id-slips/{kitting_no}", { params: { path: { kitting_no: kittingNo } } })
      .then(({ data, error: e }) => {
        if (!alive) return;
        if (data) { setSlip(data); setSel(initialSelection(data)); }
        else setError(typeof e?.detail === "string" ? e.detail : t("idslip.loadError"));
      })
      .catch(() => alive && setError(t("error.connection")));
    return () => { alive = false; };
  }, [kittingNo, t]);

  // 押した種類は、種類やロットを選び直すまで覚えておく(afterprint で戻さない)。Chrome の印刷の画面は、用紙などを変えるたびに
  // beforeprint / afterprint を飛ばして組み直すので、戻すと全部の種類(同じ識別票を含む)が重なって出てしまう。詳細: docs/design/id-slips.md
  const print = (kind: SlipKind) => {
    flushSync(() => setPrinting(kind));
    window.print();
  };

  return (
    <div className="idslip-page" data-printing={printing ?? undefined}>
      {slip && sel && <IdSlipToolbar slip={slip} sel={sel} onChange={(next) => { setPrinting(null); setSel(next); }} onPrint={print} />}
      {error && <Notice kind="error">{error}</Notice>}
      {!slip && !error && <p className="placeholder">{t("common.loading")}</p>}
      {slip && sel && sel.kinds.map((kind) => (
        <section key={kind} className={`idslip-group${printing === kind ? " is-printing" : ""}`} data-kind={kind} aria-label={t(`idslip.kind.${kind}`)}>
          {pagesOf(kind, sel).map((p, i) => <Page key={`${p.lot}:${i}`} kind={kind} slip={slip} lotNo={p.lot} />)}
        </section>
      ))}
    </div>
  );
}
