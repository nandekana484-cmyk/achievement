// ダッシュボード: 生産ラインを選ぶ(ラインの一覧はマスタから読む)。表示言語もここで切り替えられる。
import { Link } from "react-router-dom";
import { useI18n } from "../i18n/I18nProvider";
import { LanguageSwitch } from "../i18n/LanguageSwitch";
import { Notice } from "../shared/Notice";
import { useMasters } from "../shared/useMasters";

export function Dashboard() {
  const { masters, error } = useMasters();
  const { t } = useI18n();
  return (
    <main className="dashboard">
      <div className="dashboard-head">
        <h1>{t("dashboard.title")}</h1>
        <LanguageSwitch />
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      {!masters && !error && <p className="placeholder">{t("common.loading")}</p>}
      {masters && masters.lines.length === 0 && <Notice kind="info">{t("dashboard.noLines")}</Notice>}
      <ul className="line-list">
        {masters?.lines.map((l) => (
          <li key={l.line_code}>
            <Link to={`/field/lines/${encodeURIComponent(l.line_code)}`} className="line-card">
              {l.name}
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
