import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  deleteSaved, emptyState, fromQuery, hasCriteria, loadSaved, safeHighlight, saveFilter, toApiParams, toQuery,
} from "../src/lib/searchState.js";
import { badgeClass, toneFor } from "../src/lib/tone.js";

describe("search state <-> URL", () => {
  it("defaults to documents and drops unknown names", () => {
    const state = fromQuery({ tab: "nonsense", q: "công văn", evil: "1", fonds: "F-1", file_title: "chỉ của hồ sơ" });
    expect(state.tab).toBe("van-ban");
    expect(state.q).toBe("công văn");
    expect(state.filters).toEqual({ fonds: "F-1" }); // file_title is not a document filter
    expect(state.advanced).toBe(true); // a filter in the URL opens the advanced panel
  });

  it("round-trips a state through the query", () => {
    const state = { ...emptyState("ho-so"), q: " báo cáo ", sort: "newest", page: 3, filters: { fonds: "F1", status: "Nháp", catalog: "" } };
    const query = toQuery(state);
    expect(query).toEqual({ tab: "ho-so", q: "báo cáo", sort: "newest", page: "3", fonds: "F1", status: "Nháp" });
    const back = fromQuery(query);
    expect(back).toMatchObject({ tab: "ho-so", q: "báo cáo", sort: "newest", page: 3, filters: { fonds: "F1", status: "Nháp" } });
  });

  it("ignores an unknown sort and a nonsense page", () => {
    expect(fromQuery({ sort: "drop table", page: "-4" })).toMatchObject({ sort: "", page: 1 });
    expect(fromQuery({ page: "abc" }).page).toBe(1);
  });

  it("builds API parameters without empties and without foreign filters", () => {
    const state = { ...emptyState("van-ban"), q: "x", filters: { fonds: "F", author: "Sở", status: "Nháp", file_type: "" }, page: 2 };
    expect(toApiParams(state)).toEqual({ query: "x", fonds: "F", author: "Sở", page: 2, page_size: 20 });
  });

  it("knows when there is something to search for", () => {
    expect(hasCriteria(emptyState())).toBe(false);
    expect(hasCriteria({ ...emptyState(), q: "  " })).toBe(false);
    expect(hasCriteria({ ...emptyState(), filters: { fonds: "F" } })).toBe(true);
  });
});

describe("safeHighlight", () => {
  it("keeps the engine's <mark> and escapes everything else", () => {
    expect(safeHighlight("Báo <mark>cáo</mark> & <script>alert(1)</script>")).toBe(
      "Báo <mark>cáo</mark> &amp; &lt;script&gt;alert(1)&lt;/script&gt;",
    );
    expect(safeHighlight('<img src=x onerror=alert(1)>')).toBe("&lt;img src=x onerror=alert(1)&gt;");
    expect(safeHighlight(null)).toBe("");
  });
});

describe("saved filters", () => {
  beforeEach(() => localStorage.clear());

  it("saves, lists (sorted) and deletes", () => {
    saveFilter("Văn bản 2020", { ...emptyState(), q: "a", page: 4, filters: { fonds: "F" } });
    saveFilter("Báo cáo", { ...emptyState("ho-so"), q: "b" });
    expect(loadSaved().map((s) => s.name)).toEqual(["Báo cáo", "Văn bản 2020"]);
    expect(loadSaved()[1].query).toEqual({ tab: "van-ban", q: "a", fonds: "F" }); // the page is not saved
    saveFilter("Báo cáo", { ...emptyState("ho-so"), q: "new" }); // same name replaces
    expect(loadSaved()).toHaveLength(2);
    expect(loadSaved()[0].query.q).toBe("new");
    expect(deleteSaved("Báo cáo").map((s) => s.name)).toEqual(["Văn bản 2020"]);
  });

  it("ignores a blank name and survives corrupt or blocked storage", () => {
    saveFilter("   ", emptyState());
    expect(loadSaved()).toEqual([]);
    localStorage.setItem("dm-saved-filters", "{not json");
    expect(loadSaved()).toEqual([]);
    const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    expect(() => saveFilter("x", emptyState())).not.toThrow();
    spy.mockRestore();
  });
});

describe("status badges", () => {
  it("colours the states the archive uses", () => {
    expect(toneFor("Đã index")).toBe("success");
    expect(toneFor("Lỗi")).toBe("danger");
    expect(toneFor("Đang xử lý")).toBe("info");
    expect(toneFor("Nháp")).toBe("muted");
    expect(badgeClass("Cảnh báo tiêu hủy")).toBe("badge badge-warning");
  });
});
