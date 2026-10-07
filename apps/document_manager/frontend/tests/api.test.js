import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, call, errorMessage, serverMessages, stripHtml } from "../src/lib/api.js";

const reply = (body, status = 200) => ({
  status,
  ok: status >= 200 && status < 300,
  json: async () => body,
});

afterEach(() => vi.restoreAllMocks());

describe("stripHtml", () => {
  it("turns the HTML of a Frappe message into plain text", () => {
    const html = 'Cannot delete because <a href="/x">Agency A</a> is linked with Fonds&nbsp;<b>F-1</b><br>Retry &amp; check';
    expect(stripHtml(html)).toBe("Cannot delete because Agency A is linked with Fonds F-1\nRetry & check");
  });
  it("copes with empty input", () => {
    expect(stripHtml(null)).toBe("");
    expect(stripHtml(undefined)).toBe("");
  });
});

describe("server messages", () => {
  const payload = {
    _server_messages: JSON.stringify([
      JSON.stringify({ message: "Giá trị <b>X</b> đã có", indicator: "red" }),
      JSON.stringify({ message: "Lần hai" }),
    ]),
  };
  it("are unpacked from the doubly encoded _server_messages", () => {
    expect(serverMessages(payload)).toEqual(["Giá trị X đã có", "Lần hai"]);
  });
  it("tolerate garbage", () => {
    expect(serverMessages({ _server_messages: "not json" })).toEqual([]);
    expect(serverMessages({})).toEqual([]);
    expect(serverMessages(null)).toEqual([]);
  });
  it("win over the generic text of a status", () => {
    expect(errorMessage(payload, 417)).toBe("Giá trị X đã có\nLần hai");
  });
  it("fall back to a readable sentence per status", () => {
    expect(errorMessage({}, 403)).toMatch(/không có quyền/);
    expect(errorMessage({}, 404)).toMatch(/Không tìm thấy/);
    expect(errorMessage({ exc_type: "TimestampMismatchError" }, 417)).toMatch(/người khác thay đổi/);
    expect(errorMessage({}, 500)).toMatch(/Máy chủ/);
  });
});

describe("call", () => {
  it("sends reads as GET with JSON-encoded objects and skips empty values", async () => {
    const fetcher = vi.fn().mockResolvedValue(reply({ message: { ok: true } }));
    const result = await call("a.b.c", { doctype: "Fonds", filters: { status: "x" }, search: "", page: 2, none: null }, { fetcher });
    expect(result).toEqual({ ok: true });
    const [url, init] = fetcher.mock.calls[0];
    expect(init.method).toBe("GET");
    const query = new URLSearchParams(url.split("?")[1]);
    expect(url.startsWith("/api/method/a.b.c?")).toBe(true);
    expect(query.get("doctype")).toBe("Fonds");
    expect(query.get("filters")).toBe('{"status":"x"}');
    expect(query.get("page")).toBe("2");
    expect(query.has("search")).toBe(false);
    expect(query.has("none")).toBe(false);
  });

  it("sends writes as POST with a JSON body and the CSRF header", async () => {
    const fetcher = vi.fn().mockResolvedValue(reply({ message: 1 }));
    await call("a.b.save", { values: { n: 1 } }, { post: true, fetcher });
    const [url, init] = fetcher.mock.calls[0];
    expect(url).toBe("/api/method/a.b.save");
    expect(init.method).toBe("POST");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(init.headers).toHaveProperty("X-Frappe-CSRF-Token");
    expect(JSON.parse(init.body)).toEqual({ values: { n: 1 } });
  });

  it("raises an ApiError carrying the server's explanation", async () => {
    const body = { exc_type: "ValidationError", _server_messages: JSON.stringify([JSON.stringify({ message: "Sai rồi" })]) };
    const fetcher = vi.fn().mockResolvedValue(reply(body, 417));
    const error = await call("x", {}, { fetcher }).catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.message).toBe("Sai rồi");
    expect(error.status).toBe(417);
    expect(error.excType).toBe("ValidationError");
  });

  it("explains a network failure", async () => {
    const fetcher = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    const error = await call("x", {}, { fetcher }).catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.message).toMatch(/kết nối/);
  });

  it("lets a call opt out of the login redirect (a wrong current password answers 401)", async () => {
    const assign = vi.fn();
    vi.stubGlobal("location", { pathname: "/dashboard", search: "", assign });
    const body = { _server_messages: JSON.stringify([JSON.stringify({ message: "Incorrect password" })]) };
    const fetcher = vi.fn().mockResolvedValue(reply(body, 401));
    const error = await call("x", {}, { fetcher, loginOn401: false }).catch((e) => e);
    expect(assign).not.toHaveBeenCalled();
    expect(error.message).toBe("Incorrect password");
    vi.unstubAllGlobals();
  });

  it("sends an expired session to the login page and returns to where the user was", async () => {
    const assign = vi.fn();
    vi.stubGlobal("location", { pathname: "/dashboard/danh-muc/tu-dien", search: "?a=1", assign });
    const fetcher = vi.fn().mockResolvedValue(reply({}, 401));
    await call("x", {}, { fetcher }).catch(() => {});
    expect(assign).toHaveBeenCalledWith("/dang-nhap?redirect-to=%2Fdashboard%2Fdanh-muc%2Ftu-dien%3Fa%3D1");
    vi.unstubAllGlobals();
  });
});
