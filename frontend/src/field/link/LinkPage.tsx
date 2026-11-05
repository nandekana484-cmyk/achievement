// 面1と面2の紐づけのページ(/field/link/:kittingNo。2回目の計画)。ライン画面の「紐づけ」と、生産記録票の「1回目と紐づける」から開く。
// 紐づけたあとは「戻る」で、開いた元(ライン画面または生産記録票)へ戻る。詳細: docs/design/line-screen.md
import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useI18n } from "../../i18n/I18nProvider";
import { LanguageSwitch } from "../../i18n/LanguageSwitch";
import { api, type BoardPlan } from "../../shared/api";
import { Notice } from "../../shared/Notice";
import { initialWorkerId, safeBack, type SideLinkView } from "../line/sideLink";
import { LinkForm } from "./LinkForm";

export function LinkPage() {
  const { kittingNo = "" } = useParams();
  const [params] = useSearchParams();
  const { t } = useI18n();
  const [plan, setPlan] = useState<BoardPlan | null>(null);
  const [view, setView] = useState<SideLinkView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [workerId, setWorkerId] = useState(() => initialWorkerId(params)); // ライン画面から開いたときは、今の担当者。ページにいる間は残す

  useEffect(() => {
    let alive = true;
    api.GET("/api/runs/{kitting_no}", { params: { path: { kitting_no: kittingNo } } })
      .then(({ data, error: e }) => {
        if (!alive) return;
        if (data) { setPlan(data); setView(data.side_link ?? null); }
        else setError(typeof e?.detail === "string" ? e.detail : t("link.loadError"));
      })
      .catch(() => alive && setError(t("error.connection")));
    return () => { alive = false; };
  }, [kittingNo, t]);

  const line = plan?.plan.line_code;
  const back = safeBack(params.get("back")) ?? (line ? `/field/lines/${encodeURIComponent(line)}?kitting_no=${encodeURIComponent(kittingNo)}` : "/field");
  return (
    <main className="link-page">
      <div className="dashboard-head">
        <h1>{t("link.title")}</h1>
        <LanguageSwitch />
      </div>
      <p className="link-head">
        <Link to={back} className="btn">{t("link.back")}</Link>
        <strong>{kittingNo}</strong>
        {plan && <span>{plan.plan.product_name}</span>}
        {plan && <span>{plan.plan.line_code} / {t("link.run", { run: plan.plan.run_no })}</span>}
      </p>
      {error && <Notice kind="error">{error}</Notice>}
      {!plan && !error && <p className="placeholder">{t("common.loading")}</p>}
      {plan && (!view || view.role !== "side2") && <Notice kind="info">{t("link.notSide2")}</Notice>}
      {plan && view && view.role === "side2" && (
        <LinkForm key={`${view.partner}:${view.suggested}`} kittingNo={kittingNo} view={view} onView={setView} workerId={workerId} onWorkerId={setWorkerId} />
      )}
    </main>
  );
}
