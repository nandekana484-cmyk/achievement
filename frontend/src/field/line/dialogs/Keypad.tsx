// 大きなテンキー(数の表示とキー)。NumberPadDialog と NgDialog で使う。
type Props = { text: string; onChange: (text: string) => void; disabled?: boolean };

const KEYS = ["7", "8", "9", "4", "5", "6", "1", "2", "3", "0", "00"];
const MAX_DIGITS = 6;

export function Keypad({ text, onChange, disabled }: Props) {
  const press = (k: string) => onChange((text + k).replace(/^0+(?=\d)/, "").slice(0, MAX_DIGITS));
  return (
    <>
      <output className="pad-display" aria-label="入力した数">{text === "" ? "—" : text}</output>
      <div className="pad">
        {KEYS.map((k) => (
          <button key={k} type="button" className="btn pad-key" disabled={disabled} onClick={() => press(k)}>
            {k}
          </button>
        ))}
        <button type="button" className="btn pad-key" disabled={disabled} onClick={() => onChange(text.slice(0, -1))} aria-label="1文字消す">
          ←
        </button>
        <button type="button" className="btn pad-key pad-clear" disabled={disabled} onClick={() => onChange("")}>
          クリア
        </button>
      </div>
    </>
  );
}
