// 生産記録票の印刷用のページ。「印刷」で window.print を呼ぶ(PDF の生成やサーバー側の印刷はしない)。
// 面1とつながっていない面2は、2回目だけを埋めて出し、印刷に出ない所に「1回目と紐づける」を置く。
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useI18n } from "../i18n/I18nProvider";
import { api } from "../shared/api";
import { Notice } from "../shared/Notice";
import { type Density, denserIfOverflow, type Sheet } from "./recordLayout";
import { showAllocation } from "./allocationEdit";
import { linkScreenUrl } from "./recordList";
import { RecordAllocation } from "./RecordAllocation";
import { RecordSheet } from "./RecordSheet";

export function RecordPage() {
  const { kittingNo = "" } = useParams();
  const [params] = useSearchParams();
  const { t } = useI18n();
  const [sheet, setSheet] = useState<Sheet | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0); // 割り振りを保存したあと、シートを読み直す

  useEffect(() => {
    let alive = true;
    api.GET("/api/production-records/{kitting_no}", { params: { path: { kitting_no: kittingNo } } })
      .then(({ data, error: e }) => {
        if (!alive) return;
        if (data) setSheet(data);
        else setError(typeof e?.detail === "string" ? e.detail : t("record.loadError"));
      })
      .catch(() => alive && setError(t("error.connection")));
    return () => { alive = false; };
  }, [kittingNo, t, reload]);

  // 1枚の A4 に収まるまで、行の高さと文字を縮める(収まる高さは、描いたあとに測る)
  const body = useRef<HTMLDivElement>(null);
  const [density, setDensity] = useState<Density>("normal");
  useEffect(() => setDensity("normal"), [sheet]);
  useLayoutEffect(() => {
    const height = body.current?.firstElementChild?.getBoundingClientRect().height ?? 0;
    const next = denserIfOverflow(density, height);
    if (next) setDensity(next);
  }, [sheet, density]);

  const backLine = params.get("line");
  const listUrl = `/field/print/production-record${backLine ? `?line=${encodeURIComponent(backLine)}` : ""}`;
  return (
    <div className="record-page">
      <div className="record-toolbar">
        <Link to={listUrl} className="btn">{t("record.back")}</Link>
        <button type="button" className="btn btn-primary" disabled={!sheet} onClick={() => window.print()}>{t("record.print")}</button>
        {sheet?.side2_unlinked && sheet.side2 && (
          <p className="record-unlinked">
            <span>{t("record.unlinkedNotice")}</span>
            <Link className="btn" to={linkScreenUrl(sheet.side2.kitting_no, kittingNo)}>{t("record.linkFirst")}</Link>
          </p>
        )}
        <p className="record-hint">{t("record.printHint")}</p>
      </div>
      {showAllocation(sheet?.allocation) && <RecordAllocation key={sheet.allocation.kitting_no} allocation={sheet.allocation} onChanged={() => setReload(reload + 1)} />}
      {error && <Notice kind="error">{error}</Notice>}
      {!sheet && !error && <p className="placeholder">{t("common.loading")}</p>}
      {sheet && <div className="record-body" ref={body}><RecordSheet sheet={sheet} density={density} /></div>}
    </div>
  );
}
