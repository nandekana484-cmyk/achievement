// 時刻を大きなボタンで変える部品(キーボードを使わずに直せるように)。±1時間、±10分、±1分。
// 今より後になるボタンは押せない(未来の時刻はサーバーも受け付けない)。
import { useI18n } from "../../../i18n/I18nProvider";
import { formatMDHM } from "../timeScale";

type Props = {
  label: string;
  valueMs: number;
  originalMs?: number | null; // 元の時刻(変えたら並べて出す)
  maxMs: number;
  onChange: (ms: number) => void;
  disabled?: boolean;
};

const MINUTE = 60_000;
const STEPS = [-10, -1, 1, 10];

export function TimeStepper({ label, valueMs, originalMs, maxMs, onChange, disabled }: Props) {
  const { t } = useI18n();
  const shift = (minutes: number) => onChange(valueMs + minutes * MINUTE);
  const can = (minutes: number) => !disabled && valueMs + minutes * MINUTE <= maxMs;
  const changed = originalMs != null && Math.floor(originalMs / MINUTE) !== Math.floor(valueMs / MINUTE);
  return (
    <div className="time-stepper" role="group" aria-label={t("timeStepper.aria", { label })}>
      <div className="time-stepper-head">
        <span className="time-stepper-label">{label}</span>
        <output className={`time-stepper-value${changed ? " time-changed" : ""}`}>{formatMDHM(valueMs)}</output>
        {changed && <span className="time-stepper-original">{t("timeStepper.original", { time: formatMDHM(originalMs) })}</span>}
      </div>
      <div className="time-stepper-hours">
        <button type="button" className="btn" disabled={!can(-60)} onClick={() => shift(-60)}>{t("timeStepper.hourMinus")}</button>
        <button type="button" className="btn" disabled={!can(60)} onClick={() => shift(60)}>{t("timeStepper.hourPlus")}</button>
      </div>
      <div className="time-stepper-minutes">
        {STEPS.map((m) => (
          <button key={m} type="button" className="btn" disabled={!can(m)} onClick={() => shift(m)}>
            {t("timeStepper.minutes", { sign: m < 0 ? "−" : "+", n: Math.abs(m) })}
          </button>
        ))}
      </div>
    </div>
  );
}
