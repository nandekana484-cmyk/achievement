// 面1と面2の紐づけの入口(ライン画面)。2回目(面2)の計画には「紐づけ」のボタン(今の状態つき)を出し、別のページ(/field/link/...)で紐づける。
// 1回目(面1)の計画には、紐づいた2回目を表示するだけ。詳細: docs/design/line-screen.md、docs/design/actuals-export.md
import { Link } from "react-router-dom";
import { useI18n } from "../../i18n/I18nProvider";
import type { BoardPlan } from "../../shared/api";
import { linkButtonState, linkPageUrl } from "./sideLink";

/** 面1の計画: 紐づいた2回目の表示だけ。 */
export function SideLinkNote({ plan }: { plan: BoardPlan }) {
  const { t } = useI18n();
  const v = plan.side_link;
  return v?.role === "side1" && v.partner ? <p className="side-link">{t("sideLink.side1Partner", { partner: v.partner })}</p> : null;
}

/** 面2の計画: 「紐づけ」のボタンと今の状態(「未紐づけ」「紐づけ済み」)。 */
export function SideLinkButton({ plan }: { plan: BoardPlan }) {
  const { t } = useI18n();
  const v = plan.side_link;
  if (!v || v.role !== "side2") return null;
  const state = linkButtonState(v);
  return (
    <Link className="btn btn-small side-link-button" to={linkPageUrl(plan.plan.kitting_no)} aria-label={`${t("sideLink.button")} ${t(`sideLink.state.${state}`)}`}>
      {t("sideLink.button")}
      <span className={`side-link-state side-link-state-${state}`}>{t(`sideLink.state.${state}`)}</span>
    </Link>
  );
}
