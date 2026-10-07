import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import TableInput from "../src/components/TableInput.vue";
import { blankRecord, blankRow, isoDate, isVisible, missingRequired } from "../src/lib/doctype.js";
import {
  actionStyle, approvedCount, confirmText, counter, daysLate, decisionsFrom, dueText, kindOf, needsConfirm, needsReason, pickView,
  rejectedWithoutReason,
} from "../src/lib/slips.js";
import { toneFor } from "../src/lib/tone.js";

describe("slip helpers", () => {
  it("knows the two kinds of slip, defaulting to the usage slip", () => {
    expect(kindOf("copy").doctype).toBe("Copy Request");
    expect(kindOf("usage").route).toBe("/doc-gia/phieu-su-dung");
    expect(kindOf("nonsense").kind).toBe("usage");
  });

  it("styles the workflow actions by what they do", () => {
    for (const a of ["Duyệt", "Giao tài liệu", "Nhận trả", "Chuyển lãnh đạo"]) expect(actionStyle(a)).toBe("btn-primary");
    for (const a of ["Từ chối", "Hủy phiếu"]) expect(actionStyle(a)).toBe("btn-danger");
    expect(actionStyle("Trả lại phòng đọc")).toBe("");
  });

  it("asks for a reason only when turning a slip down, and confirms the actions that cannot be undone", () => {
    expect(needsReason("Từ chối")).toBe(true);
    expect(needsReason("Duyệt")).toBe(false);
    expect(["Hủy phiếu", "Giao tài liệu", "Hoàn thành"].every(needsConfirm)).toBe(true);
    expect(needsConfirm("Duyệt")).toBe(false);
    const slip = { doctype: "Usage Request", name: "UR-1", reader: { full_name: "An" } };
    expect(confirmText("Giao tài liệu", slip)).toContain("UR-1");
    expect(confirmText("Giao tài liệu", slip)).toContain("An");
  });

  it("turns the item decisions into what the API expects", () => {
    const items = [
      { row: "a", item_status: "Đã duyệt", decision_note: "" },
      { row: "b", item_status: "Từ chối", decision_note: "" },
      { row: "c", item_status: "Từ chối", decision_note: "Đang tu bổ" },
      { row: "d", item_status: "Chờ duyệt" },
    ];
    expect(decisionsFrom(items)[3]).toEqual({ row: "d", status: "Chờ duyệt", note: "" });
    expect(rejectedWithoutReason(items).map((i) => i.row)).toEqual(["b"]);
    expect(approvedCount(items)).toBe(2); // the two not turned down will be approved with the slip
  });

  it("counts days late from the due date", () => {
    const today = new Date(2026, 9, 7);
    expect(daysLate("2026-10-04", today)).toBe(3);
    expect(daysLate("2026-10-07", today)).toBe(0);
    expect(daysLate("2026-10-20", today)).toBe(0); // not due yet
    expect(daysLate(null, today)).toBe(0);
    expect(dueText({ due_date: "2000-01-01", is_overdue: 1 })).toMatch(/^quá \d+ ngày$/);
    expect(dueText({ due_date: "2000-01-01", is_overdue: 0 })).toBe("");
  });

  it("picks the requested view when it exists, else the server's suggestion", () => {
    const views = [{ view: "cho_tiep_nhan" }, { view: "qua_han" }];
    expect(pickView("qua_han", views, "cho_tiep_nhan")).toBe("qua_han");
    expect(pickView("bogus", views, "cho_tiep_nhan")).toBe("cho_tiep_nhan");
    expect(pickView(undefined, views, "cho_lanh_dao")).toBe("cho_lanh_dao");
  });

  it("shows tab counters compactly", () => {
    expect(counter(0)).toBe("");
    expect(counter(7)).toBe(7);
    expect(counter(150)).toBe("99+");
  });

  it("colours every state of a slip", () => {
    expect(toneFor("Chờ lãnh đạo duyệt")).toBe("warning");
    expect(toneFor("Đang sử dụng")).toBe("info");
    expect(toneFor("Đã trả")).toBe("success");
    expect(toneFor("Từ chối")).toBe("danger");
    expect(toneFor("Nháp")).toBe("muted");
  });
});

describe("child tables in forms", () => {
  const columns = [
    { fieldname: "fonds", fieldtype: "Link", options: "Fonds", label: "Phông", reqd: 1, read_only: false },
    { fieldname: "level", fieldtype: "Int", label: "Mức", default: "2", read_only: false },
    { fieldname: "active", fieldtype: "Check", label: "Dùng", default: "1", read_only: false },
    { fieldname: "label", fieldtype: "Data", label: "Nhãn", read_only: true },
  ];
  const field = { fieldname: "rows", fieldtype: "Table", label: "Các dòng", reqd: 0, read_only: false, table: { doctype: "X", columns } };

  it("starts a row from the column defaults", () => {
    expect(blankRow(columns)).toEqual({ fonds: "", level: 2, active: 1, label: "" });
  });

  it("starts a record with empty tables and asks for rows only when the table is required", () => {
    const meta = { fields: [field, { fieldname: "name2", fieldtype: "Data", label: "Tên", reqd: 1 }] };
    expect(blankRecord(meta).rows).toEqual([]);
    expect(missingRequired(meta, { rows: [], name2: "x" })).toEqual([]);
    meta.fields[0] = { ...field, reqd: 1 };
    expect(missingRequired(meta, { rows: [], name2: "x" }).map((m) => m.fieldname)).toEqual(["rows"]);
    expect(missingRequired(meta, { rows: [{ fonds: "F" }], name2: "x" })).toEqual([]);
  });

  it("adds, edits and removes rows without touching the original array", async () => {
    const original = [{ fonds: "A", level: 1, active: 1, label: "" }];
    const wrapper = mount(TableInput, { props: { field, modelValue: original }, global: { stubs: { LinkSelect: true } } });
    await wrapper.find("button.btn:not(.btn-icon)").trigger("click"); // Thêm dòng
    let [emitted] = wrapper.emitted("update:modelValue").at(-1);
    expect(emitted).toHaveLength(2);
    expect(emitted[1]).toEqual({ fonds: "", level: 2, active: 1, label: "" });

    await wrapper.find("input[type=number]").setValue("5");
    [emitted] = wrapper.emitted("update:modelValue").at(-1);
    expect(emitted[0].level).toBe(5);

    await wrapper.find("button.btn-icon").trigger("click"); // remove the only row
    [emitted] = wrapper.emitted("update:modelValue").at(-1);
    expect(emitted).toEqual([]);
    expect(original).toHaveLength(1);
  });

  it("is read-only when the form is", () => {
    const wrapper = mount(TableInput, { props: { field, modelValue: [{ fonds: "A" }], disabled: true }, global: { stubs: { LinkSelect: true } } });
    expect(wrapper.find("button.btn-icon").exists()).toBe(false);
    expect(wrapper.text()).not.toContain("Thêm dòng");
    expect(wrapper.find("input[type=number]").attributes("disabled")).toBeDefined();
  });
});

describe("forms that depend on a value", () => {
  it("shows a field only when its depends_on holds", () => {
    const record = { kind: "Đăng ký độc giả", active: 1, name: "", note: "x" };
    expect(isVisible("", record)).toBe(true);
    expect(isVisible("eval:doc.kind == 'Đăng ký độc giả'", record)).toBe(true);
    expect(isVisible("eval:doc.kind != 'Đăng ký độc giả'", record)).toBe(false);
    expect(isVisible("eval:doc.kind=='Phiếu sao chụp'", record)).toBe(false);
    expect(isVisible('eval:doc.kind === "Đăng ký độc giả"', record)).toBe(true);
    expect(isVisible("eval:doc.active == 1", record)).toBe(true);
    expect(isVisible("eval:doc.active", record)).toBe(true);
    expect(isVisible("note", record)).toBe(true);
    expect(isVisible("name", record)).toBe(false);
    expect(isVisible("eval:!doc.active", record)).toBe(false);
    expect(isVisible("eval:doc.a && doc.b", record)).toBe(true); // too complex to judge here: shown, the server decides
  });

  it("does not ask for a required field that is not shown", () => {
    const meta = { fields: [{ fieldname: "x", fieldtype: "Data", label: "X", reqd: 1, depends_on: "eval:doc.kind == 'a'" }] };
    expect(missingRequired(meta, { kind: "b", x: "" })).toEqual([]);
    expect(missingRequired(meta, { kind: "a", x: "" }).map((m) => m.fieldname)).toEqual(["x"]);
  });

  it("starts a date field with today's date, not the word Today", () => {
    const meta = { fields: [{ fieldname: "d", fieldtype: "Date", default: "Today" }, { fieldname: "t", fieldtype: "Datetime", default: "Now" }] };
    const record = blankRecord(meta);
    expect(record.d).toBe(isoDate());
    expect(record.t).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/);
    expect(isoDate(new Date(2026, 0, 5))).toBe("2026-01-05");
  });
});
