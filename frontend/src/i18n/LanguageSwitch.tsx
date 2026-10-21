// 表示言語の切り替え(「日本語 / Tiếng Việt」)。ライン選択の画面と、ライン画面の上部に置く。
import { useI18n } from "./I18nProvider";
import { LANG_NAMES, LANGS } from "./translate";

export function LanguageSwitch() {
  const { lang, setLang, t } = useI18n();
  return (
    <div className="lang-switch" role="group" aria-label={t("lang.switch")}>
      {LANGS.map((l) => (
        <button key={l} type="button" lang={l} className={`lang-button${l === lang ? " lang-current" : ""}`}
          aria-pressed={l === lang} onClick={() => setLang(l)}>
          {LANG_NAMES[l]}
        </button>
      ))}
    </div>
  );
}
