// サーバーが返したファイル(CSV など)を、ブラウザに保存させる。ファイル名はサーバーが付けたもの。

export function filenameOf(response: Response, fallback: string): string {
  const m = /filename="([^"]+)"/.exec(response.headers.get("content-disposition") ?? "");
  return m ? m[1] : fallback;
}

export function saveBlob(blob: Blob, name: string): void {
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  a.click();
  URL.revokeObjectURL(url);
}
