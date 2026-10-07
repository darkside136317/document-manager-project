import { afterEach, describe, expect, it, vi } from "vitest";
import { blankRecord, formFieldNames, missingRequired, selectOptions } from "../src/lib/doctype.js";
import { debounce, displayValue, formatDate, formatDateTime, formatNumber, truncate } from "../src/lib/format.js";
import { initials } from "../src/lib/boot.js";

const meta = {
  fields: [
    { fieldname: "name_field", fieldtype: "Data", reqd: 1, label: "Tên", default: undefined },
    { fieldname: "is_active", fieldtype: "Check", default: "1" },
    { fieldname: "is_group", fieldtype: "Check", default: "0" },
    { fieldname: "years", fieldtype: "Int", default: "5" },
    { fieldname: "ratio", fieldtype: "Float" },
    { fieldname: "kind", fieldtype: "Select", options: "\nA\nB", default: "A" },
    { fieldname: "parent", fieldtype: "Link", options: "X", reqd: 1, label: "Cha" },
    { fieldname: "locked", fieldtype: "Data", reqd: 1, read_only: true },
    { fieldname: "flag", fieldtype: "Check", reqd: 1, label: "Cờ" },
  ],
  layout: [
    { title: "A", columns: [["name_field", "is_active"], ["years"]] },
    { title: null, columns: [["kind"]] },
  ],
};

describe("doctype helpers", () => {
  it("builds a blank record from the DocType defaults", () => {
    expect(blankRecord(meta)).toMatchObject({
      name_field: "", is_active: 1, is_group: 0, years: 5, ratio: null, kind: "A", parent: "",
    });
  });
  it("lets overrides win (a child created under a parent)", () => {
    expect(blankRecord(meta, { parent: "P1", is_active: 0 })).toMatchObject({ parent: "P1", is_active: 0 });
  });
  it("splits Select options as stored: one per line, the first may be blank", () => {
    expect(selectOptions({ options: "\nA\nB" })).toEqual(["", "A", "B"]);
    expect(selectOptions({})).toEqual([""]);
  });
  it("lists the form fields in layout order", () => {
    expect(formFieldNames(meta)).toEqual(["name_field", "is_active", "years", "kind"]);
  });
  it("reports required fields that are empty, ignoring read-only fields and checkboxes", () => {
    const missing = missingRequired(meta, { name_field: "", parent: null, locked: "", flag: 0 });
    expect(missing.map((m) => m.fieldname)).toEqual(["name_field", "parent"]);
    expect(missingRequired(meta, { name_field: "x", parent: "p" })).toEqual([]);
  });
});

describe("formatting", () => {
  it("formats dates and datetimes the Vietnamese way", () => {
    expect(formatDate("2026-10-07")).toBe("07/10/2026");
    expect(formatDateTime("2026-10-07 14:05:09.123")).toBe("07/10/2026 14:05");
    expect(formatDate("")).toBe("");
    expect(formatDate("garbage")).toBe("garbage");
  });
  it("groups numbers", () => {
    expect(formatNumber(1234567)).toBe(new Intl.NumberFormat("vi-VN").format(1234567));
    expect(formatNumber(null)).toBe("0");
  });
  it("truncates and strips tags", () => {
    expect(truncate("<p>Xin   chào</p>", 50)).toBe("Xin chào");
    expect(truncate("a".repeat(100), 10)).toBe(`${"a".repeat(9)}…`);
  });
  it("shows a value according to the field type", () => {
    expect(displayValue({ fieldtype: "Check" }, 1)).toBe("Có");
    expect(displayValue({ fieldtype: "Check" }, 0)).toBe("Không");
    expect(displayValue({ fieldtype: "Date" }, "2026-01-02")).toBe("02/01/2026");
    expect(displayValue({ fieldtype: "Data" }, "x")).toBe("x");
    expect(displayValue({ fieldtype: "Data" }, null)).toBe("");
  });
  it("makes initials", () => {
    expect(initials("Nguyễn Văn An")).toBe("NA");
    expect(initials("admin")).toBe("A");
    expect(initials("")).toBe("?");
  });
});

describe("debounce", () => {
  afterEach(() => vi.useRealTimers());
  it("runs once after the last call and can be cancelled", () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const soon = debounce(fn, 200);
    soon("a");
    soon("b");
    vi.advanceTimersByTime(199);
    expect(fn).not.toHaveBeenCalled();
    vi.advanceTimersByTime(2);
    expect(fn).toHaveBeenCalledTimes(1);
    expect(fn).toHaveBeenCalledWith("b");
    soon("c");
    soon.cancel();
    vi.advanceTimersByTime(500);
    expect(fn).toHaveBeenCalledTimes(1);
  });
});
