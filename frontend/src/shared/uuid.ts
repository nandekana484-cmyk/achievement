// request_id に使う UUID v4。crypto.randomUUID は安全な接続(HTTPS)でしか使えないので、
// HTTP の社内LANでも使える crypto.getRandomValues から作る。

type FillRandom = (bytes: Uint8Array) => Uint8Array;

const defaultFill: FillRandom = (bytes) => crypto.getRandomValues(bytes);

/** UUID v4 の文字列(例: 3b241101-e2bb-4255-8caf-4136c566a962)を作る。 */
export function uuidv4(fill: FillRandom = defaultFill): string {
  const b = fill(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40; // 版 4
  b[8] = (b[8] & 0x3f) | 0x80; // 変種 RFC 4122
  const hex = Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
