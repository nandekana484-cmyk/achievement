import { describe, expect, it, vi } from "vitest";
import { makeTranslate } from "../i18n/translate";
import { type ApiResult, failureMessage, RequestIdStore, sendWithRetry } from "./send";

const t = makeTranslate("ja");

const reply = <T>(status: number, body: unknown): ApiResult<T> => ({
  response: new Response(null, { status }),
  ...(status < 400 ? { data: body as T } : { error: body }),
});

describe("sendWithRetry", () => {
  it("成功したらそのまま返す(送り直さない)", async () => {
    const call = vi.fn().mockResolvedValue(reply(200, { id: 1 }));
    expect(await sendWithRetry(call)).toEqual({ ok: true, data: { id: 1 } });
    expect(call).toHaveBeenCalledTimes(1);
  });

  it("通信の失敗は1回だけ送り直し、成功すればよい", async () => {
    const call = vi.fn().mockRejectedValueOnce(new TypeError("Failed to fetch")).mockResolvedValue(reply(200, "ok"));
    expect(await sendWithRetry(call)).toEqual({ ok: true, data: "ok" });
    expect(call).toHaveBeenCalledTimes(2);
  });

  it("503 は1回だけ送り直し、それでも 503 なら理由を返す", async () => {
    const call = vi.fn().mockResolvedValue(reply(503, { detail: "他の処理と重なりました" }));
    expect(await sendWithRetry(call)).toEqual({ ok: false, status: 503, detail: "他の処理と重なりました", retryable: true });
    expect(call).toHaveBeenCalledTimes(2);
  });

  it("通信の失敗が続いたら、通信できない旨を返す", async () => {
    const call = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    expect(await sendWithRetry(call)).toMatchObject({ ok: false, status: null, detail: null });
    expect(call).toHaveBeenCalledTimes(2);
  });

  it.each([409, 404])("%i は送り直さず、detail をそのまま返す", async (status) => {
    const call = vi.fn().mockResolvedValue(reply(status, { detail: "担当者が設定されていません" }));
    expect(await sendWithRetry(call)).toEqual({ ok: false, status, detail: "担当者が設定されていません", retryable: false });
    expect(call).toHaveBeenCalledTimes(1);
  });

  it("422 や 500 は送り直さず、サーバーの理由の文は使わない", async () => {
    expect(await sendWithRetry(vi.fn().mockResolvedValue(reply(422, { detail: [{ msg: "x" }] })))).toMatchObject({ status: 422, detail: null });
    const call = vi.fn().mockResolvedValue(reply(500, { detail: "内部の情報" }));
    expect(await sendWithRetry(call)).toMatchObject({ status: 500, detail: null });
    expect(call).toHaveBeenCalledTimes(1);
  });
});

describe("failureMessage", () => {
  it("サーバーの理由の文は、どの言語でも訳さずにそのまま出す", () => {
    for (const lang of ["ja", "vi"] as const) {
      expect(failureMessage({ status: 409, detail: "担当者が設定されていません" }, makeTranslate(lang))).toBe("担当者が設定されていません");
    }
  });

  it("理由の文が無ければ、選んだ言語の決まった文", () => {
    expect(failureMessage({ status: null, detail: null }, t)).toBe("通信できませんでした。電波の状態を確かめて、もう一度押してください");
    expect(failureMessage({ status: 503, detail: null }, t)).toBe("他の処理と重なったため、記録できませんでした。もう一度押してください");
    expect(failureMessage({ status: 422, detail: null }, t)).toBe("入力の内容が正しくありません。入力し直してください");
    expect(failureMessage({ status: 500, detail: null }, t)).toBe("サーバーでエラーが起きました(500)。もう一度押してください");
    expect(failureMessage({ status: 404, detail: null }, t)).toBe("サーバーでエラーが起きました(404)。もう一度押してください");
    expect(failureMessage({ status: 500, detail: null }, makeTranslate("vi"))).toBe("Máy chủ bị lỗi (500). Hãy bấm lại");
  });
});

describe("RequestIdStore", () => {
  const counter = () => {
    let n = 0;
    return () => `id-${++n}`;
  };

  it("成功するまで、同じ操作・同じ内容には同じ request_id を返す", () => {
    const store = new RequestIdStore(counter());
    expect(store.idFor("start:K1:setup", { action: "start" })).toBe("id-1");
    expect(store.idFor("start:K1:setup", { action: "start" })).toBe("id-1");
    store.succeeded("start:K1:setup");
    expect(store.idFor("start:K1:setup", { action: "start" })).toBe("id-2");
  });

  it("内容が変わったら作り直す(同じ request_id で内容の違う操作を送らない)", () => {
    const store = new RequestIdStore(counter());
    expect(store.idFor("end:K1:production", { qty: 100 })).toBe("id-1");
    expect(store.idFor("end:K1:production", { qty: 120 })).toBe("id-2");
  });

  it("操作が違えば別の request_id", () => {
    const store = new RequestIdStore(counter());
    expect(store.idFor("a", {})).not.toBe(store.idFor("b", {}));
  });
});
