// 訂正の履歴の一覧(新しい順)と、読み込むフック。工程の記録と付帯作業の履歴の画面で使う。
import { useEffect, useState } from "react";
import { useI18n } from "../../../i18n/I18nProvider";
import type { Correction } from "../../../shared/api";
import { operatorLabel } from "../operatorLabel";
import { formatMDHM } from "../timeScale";
import { changeLines, KIND_KEYS, SOURCE_KEYS, targetText } from "./historyText";
import { REASON_KEYS } from "./ReasonPicker";

type Loaded = { items: Correction[] | null; error: string | null };

/** 画面を開いたときに1回読む。load は API の呼び出し(data が一覧)。 */
export function useCorrections(load: () => Promise<{ data?: Correction[] }>): Loaded {
  const { t } = useI18n();
  const [state, setState] = useState<Loaded>({ items: null, error: null });
  useEffect(() => {
    let alive = true;
    load()
      .then(({ data }) => alive && setState(data ? { items: data, error: null } : { items: null, error: t("history.loadFailed") }))
      .catch(() => alive && setState({ items: null, error: t("history.loadFailed") }));
    return () => {
      alive = false;
    };
  }, []); // 開いたときだけ
  return state;
}

export function CorrectionList({ items, error }: Loaded) {
  const { t, lang } = useI18n();
  if (error) return <p className="dialog-error" role="alert">{error}</p>;
  if (items === null) return <p>{t("common.loading")}</p>;
  if (items.length === 0) return <p className="fix-note">{t("history.none")}</p>;
  return (
    <ol className="correction-list" aria-label={t("history.corrections")}>
      {items.map((c) => (
        <li key={c.id} className={`correction-item correction-${c.kind}`}>
          <div className="correction-head">
            <span className={`badge badge-${c.kind}`}>{t(KIND_KEYS[c.kind])}</span>
            <span className="correction-target">{targetText(c, t, lang)}</span>
            <span className="correction-reason">
              {t(REASON_KEYS[c.reason] ?? "correctionReason.other")}{c.note ? `:${c.note}` : ""}
            </span>
          </div>
          {changeLines(c, t, lang).map((line) => <div key={line} className="correction-change">{line}</div>)}
          <div className="correction-meta">
            {t("history.meta", {
              time: formatMDHM(c.corrected_at),
              name: operatorLabel(c.corrected_by_name, c.corrected_by_worker_id, t),
              source: t(SOURCE_KEYS[c.source] ?? "history.source.field"),
            })}
          </div>
        </li>
      ))}
    </ol>
  );
}
