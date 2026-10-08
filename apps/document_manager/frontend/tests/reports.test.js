import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../src/lib/api.js", () => ({ api: { linkSearch: vi.fn().mockResolvedValue([]) }, call: vi.fn() }));

import BarChart from "../src/components/BarChart.vue";
import FilterForm from "../src/components/FilterForm.vue";
import {
  barWidths, cleanFilters, dependents, diffClass, downloadUrl, filterField, formatCell, initialFilters, linkFilter, printUrl,
  routeOf, signed, withFilter,
} from "../src/lib/reports.js";

const SPECS = [
  { fieldname: "fonds", label: "Phông", fieldtype: "Link", options: "Fonds" },
  { fieldname: "record_group", label: "Khối tài liệu", fieldtype: "Link", options: "Record Group", depends: "fonds" },
  { fieldname: "catalog", label: "Mục lục", fieldtype: "Link", options: "Catalog", depends: "record_group" },
  { fieldname: "group_by", label: "Theo", fieldtype: "Select", options: ["Phông", "Năm"], default: "Phông" },
  { fieldname: "status", label: "Tình trạng", fieldtype: "Select", options: ["Mới", "Đóng"] },
  { fieldname: "year_from", label: "Từ năm", fieldtype: "Int" },
  { fieldname: "only_late", label: "Chỉ quá hạn", fieldtype: "Check" },
];

beforeEach(() => vi.clearAllMocks());

describe("report filters", () => {
  it("turns a declared filter into a form field, with a blank choice only where there is no default", () => {
    expect(filterField(SPECS[3]).options).toBe("Phông\nNăm");
    expect(filterField(SPECS[4]).options).toBe("\nMới\nĐóng");
    expect(filterField(SPECS[0])).toMatchObject({ fieldtype: "Link", options: "Fonds", reqd: 0, read_only: false });
  });

  it("starts from the defaults and from what the address says", () => {
    expect(initialFilters(SPECS)).toMatchObject({ group_by: "Phông", status: "", year_from: "", only_late: 0 });
    const fromAddress = initialFilters(SPECS, { fonds: "F-1", year_from: "1990", only_late: "1", group_by: "Năm", page: "3" });
    expect(fromAddress).toMatchObject({ fonds: "F-1", year_from: 1990, only_late: 1, group_by: "Năm" });
    expect(fromAddress.page).toBeUndefined();
  });

  it("sends only filters that say something", () => {
    expect(cleanFilters({ fonds: "F-1", status: "", year_from: 0, only_late: 0, q: null, group_by: "Năm" })).toEqual({ fonds: "F-1", group_by: "Năm" });
  });

  it("restarts the filters that hang on a changed one, all the way down", () => {
    expect(dependents(SPECS, "fonds")).toEqual(["record_group"]);
    const values = { fonds: "F-1", record_group: "G-1", catalog: "C-1", group_by: "Năm" };
    expect(withFilter(SPECS, values, "fonds", "F-2")).toEqual({ fonds: "F-2", record_group: "", catalog: "", group_by: "Năm" });
    expect(withFilter(SPECS, values, "status", "Mới")).toMatchObject({ fonds: "F-1", record_group: "G-1", status: "Mới" });
    expect(values.record_group).toBe("G-1"); // the old object is left alone
  });

  it("narrows the search of a dependent filter to the value it hangs on", () => {
    expect(linkFilter(SPECS[1], { fonds: "F-1" })).toEqual({ fonds: "F-1" });
    expect(linkFilter(SPECS[1], { fonds: "" })).toBeNull();
    expect(linkFilter(SPECS[0], { fonds: "F-1" })).toBeNull();
  });

  it("draws every filter and reports a change with the dependents cleared", async () => {
    const wrapper = mount(FilterForm, { props: { filters: SPECS, modelValue: { fonds: "F-1", record_group: "G-1", catalog: "", group_by: "Phông", status: "", year_from: "", only_late: 0 } } });
    await flushPromises();
    expect(wrapper.findAll(".label, label").length).toBeGreaterThanOrEqual(SPECS.length);
    await wrapper.find("select#f-status").setValue("Mới");
    expect(wrapper.emitted("update:modelValue").at(-1)[0]).toMatchObject({ status: "Mới", fonds: "F-1" });
    await wrapper.find("form").trigger("submit");
    expect(wrapper.emitted("submit")).toHaveLength(1);
    await wrapper.findAll("button").find((b) => b.text() === "Xóa bộ lọc").trigger("click");
    expect(wrapper.emitted("reset")).toHaveLength(1);
  });
});

describe("report cells", () => {
  it("formats numbers, dates and percentages the Vietnamese way", () => {
    expect(formatCell({ fieldtype: "Int" }, 1234567)).toBe("1.234.567");
    expect(formatCell({ fieldtype: "Float" }, 1234.5)).toBe("1.234,50");
    expect(formatCell({ fieldtype: "Percent" }, 12.5)).toBe("12,5%");
    expect(formatCell({ fieldtype: "Date" }, "2026-10-07")).toBe("07/10/2026");
    expect(formatCell({ fieldtype: "Datetime" }, "2026-10-07 14:05:00")).toBe("07/10/2026 14:05");
    expect(formatCell({ fieldtype: "Data" }, null)).toBe("");
    expect(formatCell({ fieldtype: "Int" }, 0)).toBe("0");
  });

  it("links a cell to its record only when the route is complete", () => {
    expect(routeOf({ link: "/ho-so/{name}" }, { name: "AF-001" })).toBe("/ho-so/AF-001");
    expect(routeOf({ link: "/ho-so/{name}" }, { name: "a/b" })).toBe("/ho-so/a%2Fb");
    expect(routeOf({ link: "/ho-so/{name}" }, {})).toBe("");
    expect(routeOf({}, { name: "x" })).toBe("");
    expect(routeOf({ link: "{route}" }, { route: "/van-ban/DOC-1" })).toBe("/van-ban/DOC-1");
    expect(routeOf({ link: "{route}" }, { route: "//evil.example" })).toBe("");
    expect(routeOf({ link: "{route}" }, { route: "https://evil.example" })).toBe("");
  });

  it("shows a difference with its sign and colour", () => {
    expect(signed(3)).toBe("+3");
    expect(signed(-2)).toBe("-2");
    expect(signed(0)).toBe("0");
    expect(diffClass(2)).toContain("warning");
    expect(diffClass(-1)).toContain("danger");
    expect(diffClass(0)).toContain("subtle");
  });
});

describe("report output links", () => {
  it("carries the slug, the format and only the filters in use", () => {
    const url = downloadUrl("ho-so", { fonds: "F-1", status: "", only_late: 0 }, "csv");
    expect(url).toContain("api.reports.download_report?");
    const params = new URL(url, "http://x").searchParams;
    expect(params.get("slug")).toBe("ho-so");
    expect(params.get("format")).toBe("csv");
    expect(JSON.parse(params.get("filters"))).toEqual({ fonds: "F-1" });
    expect(new URL(downloadUrl("phong", {}), "http://x").searchParams.has("filters")).toBe(false);
    expect(new URL(printUrl("phong", { q: "a" }, "pdf"), "http://x").searchParams.get("format")).toBe("pdf");
  });
});

describe("bar chart", () => {
  it("scales the bars to the widest and keeps the numbers as text", () => {
    expect(barWidths([10, 5, 0])).toEqual([100, 50, 0]);
    expect(barWidths([0, 0])).toEqual([0, 0]);
    const wrapper = mount(BarChart, { props: { chart: { title: "Số văn bản theo phông", labels: ["A", "B"], datasets: [{ name: "Văn bản", values: [8, 2] }] } } });
    expect(wrapper.text()).toContain("Số văn bản theo phông");
    expect(wrapper.findAll("li")).toHaveLength(2);
    expect(wrapper.findAll("li")[1].text()).toContain("2");
    expect(wrapper.findAll("li")[0].find("[style]").attributes("style")).toContain("width: 100%");
  });
});
