import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import FieldPicker from "../src/components/FieldPicker.vue";
import JobCard from "../src/components/JobCard.vue";
import {
  allFields, countsRows, exportedLevels, fieldsPayload, isBusy, jobHeadline, jobTone, levelIndex, resultRows, toggled, watchJob,
} from "../src/lib/exchange.js";
import { toneFor } from "../src/lib/tone.js";

const LEVELS = [
  { doctype: "Fonds", label: "Phông", fields: [{ fieldname: "fonds_name", label: "Tên phông", key: true }, { fieldname: "fonds_code", label: "Mã phông", key: true }, { fieldname: "start_year", label: "Năm bắt đầu", key: false }] },
  { doctype: "Archive Document", label: "Văn bản", fields: [{ fieldname: "document_title", label: "Tiêu đề", key: true }, { fieldname: "author", label: "Tác giả", key: false }, { fieldname: "description", label: "Mô tả", key: false }] },
];

describe("choosing the levels and fields of an exchange", () => {
  it("exports a level and, when asked, everything below it", () => {
    expect(exportedLevels("Archival File", false)).toEqual(["Archival File"]);
    expect(exportedLevels("Archival File", true)).toEqual(["Archival File", "Archive Document"]);
    expect(exportedLevels("Fonds", true)).toHaveLength(5);
    expect(exportedLevels("Nonsense", true)).toEqual([]);
    expect(levelIndex("Catalog")).toBe(2);
  });

  it("starts with every field, or only those a file contains", () => {
    expect([...allFields(LEVELS).Fonds]).toEqual(["fonds_name", "fonds_code", "start_year"]);
    const found = allFields(LEVELS, { Fonds: { fonds_name: 3 }, "Archive Document": { document_title: 9, author: 2 } });
    expect([...found.Fonds]).toEqual(["fonds_name"]);
    expect([...found["Archive Document"]]).toEqual(["document_title", "author"]);
  });

  it("switches a field on and off but never a key field, and does not touch the old choice", () => {
    const choice = allFields(LEVELS);
    const off = toggled(choice, LEVELS[1], "author");
    expect(off["Archive Document"].has("author")).toBe(false);
    expect(choice["Archive Document"].has("author")).toBe(true);
    expect(toggled(off, LEVELS[1], "author")["Archive Document"].has("author")).toBe(true);
    expect(toggled(choice, LEVELS[0], "fonds_code")).toBe(choice);
  });

  it("sends the choice of the levels that are exported only", () => {
    const choice = allFields(LEVELS);
    expect(fieldsPayload(choice, ["Archive Document"])).toEqual({ "Archive Document": ["document_title", "author", "description"] });
    expect(fieldsPayload(choice, ["Catalog"])).toEqual({ Catalog: [] });
  });

  it("lists the counts of each level with the ancestors beside them", () => {
    expect(countsRows(LEVELS, { Fonds: 2 }, { Fonds: 1 })).toEqual([
      { doctype: "Fonds", label: "Phông", count: 2, ancestors: 1 },
      { doctype: "Archive Document", label: "Văn bản", count: 0, ancestors: 0 },
    ]);
  });
});

describe("how a job is told", () => {
  it("colours every status", () => {
    expect(jobTone("Hoàn thành")).toBe("success");
    expect(jobTone("Hoàn thành có lỗi")).toBe("warning");
    expect(jobTone("Thất bại")).toBe("danger");
    expect(jobTone("Đang xử lý")).toBe("info");
    expect(jobTone("Đã hủy")).toBe("muted");
    expect(toneFor("Thất bại")).toBe("danger");
    expect(toneFor("Đang kiểm kê")).toBe("info");
  });

  it("gives the headline of a running and a finished job", () => {
    expect(jobHeadline({ busy: true, status: "Đang xử lý", phase: "Đang nhập" })).toBe("Đang xử lý — Đang nhập");
    expect(jobHeadline({ busy: false, status: "Hoàn thành", summary: "Đã xuất 3 bản ghi" })).toBe("Đã xuất 3 bản ghi");
    expect(jobHeadline(null)).toBe("");
    expect(isBusy({ busy: true })).toBe(true);
    expect(isBusy(null)).toBe(false);
  });

  it("keeps only the levels a result talks about", () => {
    const job = { result: { levels: { Fonds: { created: 2, failed: 0 }, "Archive Document": { created: 0, failed: 0 } } } };
    expect(resultRows(job, LEVELS)).toEqual([{ doctype: "Fonds", label: "Phông", created: 2, failed: 0 }]);
    expect(resultRows({}, LEVELS)).toEqual([]);
  });
});

describe("following a running job", () => {
  it("asks again until the job is no longer busy, then resolves with it", async () => {
    const answers = [{ busy: true, processed: 1 }, { busy: true, processed: 5 }, { busy: false, status: "Hoàn thành" }];
    const fetch = vi.fn(async () => answers.shift());
    const seen = [];
    const timers = [];
    const watcher = watchJob("XJ-1", { fetch, onUpdate: (job) => seen.push(job.processed ?? job.status), setTimer: (fn) => timers.push(fn) });
    await vi.waitFor(() => expect(timers).toHaveLength(1));
    timers.shift()();
    await vi.waitFor(() => expect(timers).toHaveLength(1));
    timers.shift()();
    expect(await watcher.done).toEqual({ busy: false, status: "Hoàn thành" });
    expect(seen).toEqual([1, 5, "Hoàn thành"]);
    expect(fetch).toHaveBeenCalledTimes(3);
  });

  it("stops when told to and reports a failing request", async () => {
    const timers = [];
    const stopped = watchJob("XJ-2", { fetch: async () => ({ busy: true }), setTimer: (fn) => { timers.push(fn); return 1; }, clearTimer: () => {} });
    await vi.waitFor(() => expect(timers).toHaveLength(1));
    stopped.stop();
    timers.shift()();
    expect(await stopped.done).toBeNull();
    const failing = watchJob("XJ-3", { fetch: async () => { throw new Error("mất kết nối"); } });
    await expect(failing.done).rejects.toThrow("mất kết nối");
  });
});

describe("FieldPicker", () => {
  const mountPicker = (extra = {}) => mount(FieldPicker, { props: { level: LEVELS[1], chosen: new Set(["document_title", "author"]), ...extra } });

  it("shows a checkbox per field with the key fields ticked and locked", () => {
    const wrapper = mountPicker();
    const boxes = wrapper.findAll("input[type=checkbox]");
    expect(boxes).toHaveLength(3);
    expect(boxes[0].attributes("disabled")).toBeDefined();
    expect(boxes[0].element.checked).toBe(true);
    expect(boxes[2].element.checked).toBe(false);
    expect(wrapper.text()).toContain("2 / 3 trường");
  });

  it("reports a toggled field and the bulk buttons", async () => {
    const wrapper = mountPicker();
    await wrapper.findAll("input[type=checkbox]")[2].trigger("change");
    expect(wrapper.emitted("toggle")[0]).toEqual([LEVELS[1], "description"]);
    await wrapper.findAll("button").find((b) => b.text() === "Chọn tất cả").trigger("click");
    await wrapper.findAll("button").find((b) => b.text() === "Bỏ chọn").trigger("click");
    expect(wrapper.emitted("all")).toHaveLength(1);
    expect(wrapper.emitted("none")).toHaveLength(1);
  });

  it("tells two fields with the same label apart by their name", () => {
    const level = { doctype: "Archival File", label: "Hồ sơ", fields: [{ fieldname: "status", label: "Trạng thái", key: false }, { fieldname: "disposal_status", label: "Trạng thái", key: false }, { fieldname: "notes", label: "Ghi chú", key: false }] };
    const wrapper = mount(FieldPicker, { props: { level, chosen: new Set() } });
    expect(wrapper.text()).toContain("Trạng thái (status)");
    expect(wrapper.text()).toContain("Trạng thái (disposal_status)");
    expect(wrapper.text()).toContain("Ghi chú");
    expect(wrapper.text()).not.toContain("Ghi chú (notes)");
  });

  it("lists only the fields a file contains, with how many records have them", () => {
    const wrapper = mountPicker({ found: { document_title: 9, author: 2 } });
    expect(wrapper.findAll("input[type=checkbox]")).toHaveLength(2);
    expect(wrapper.text()).toContain("2");
    expect(wrapper.text()).not.toContain("Mô tả");
  });
});

describe("JobCard", () => {
  const base = { name: "XJ-2026-00001", direction: "Nhập", status: "Hoàn thành có lỗi", file_name: "phong.xml", creation: "2026-10-07 10:00:00", busy: false, has_result: false,
    summary: "Đã thêm 2, lỗi 1", finished_on: "2026-10-07 10:01:00", created: 2, updated: 0, skipped: 0, failed: 1, percent: 100, processed: 3, total: 3, file_size_kb: 12.4, checksum: "ab12",
    result: { levels: { Fonds: { created: 2, updated: 0, unchanged: 0, exists: 0, refs: 0, failed: 1, skipped: 0 } } },
    rows: [{ severity: "Lỗi", level: "Phông", path: "Phông X1", message: "Không tìm thấy cơ quan" }], rows_total: 1 };

  it("tells how an import went: counters per level and the log of failures", () => {
    const wrapper = mount(JobCard, { props: { job: base, levels: LEVELS } });
    expect(wrapper.text()).toContain("Đã thêm 2, lỗi 1");
    expect(wrapper.text()).toContain("Hoàn thành có lỗi");
    expect(wrapper.text()).toContain("Phông X1");
    expect(wrapper.text()).toContain("Không tìm thấy cơ quan");
    expect(wrapper.find("table caption").text()).toBe("Kết quả theo cấp");
    expect(wrapper.find("a[href*='download']").exists()).toBe(false);
  });

  it("shows progress and a stop button while it runs, and the download of an export once done", async () => {
    const running = mount(JobCard, { props: { job: { ...base, status: "Đang xử lý", busy: true, percent: 40, processed: 4, total: 10, phase: "Đang nhập", finished_on: null, result: null, rows: [] }, levels: LEVELS } });
    expect(running.find("[role=progressbar]").attributes("aria-valuenow")).toBe("40");
    await running.findAll("button").find((b) => b.text().includes("Dừng")).trigger("click");
    expect(running.emitted("cancel")[0][0].name).toBe("XJ-2026-00001");
    const exported = mount(JobCard, { props: { job: { ...base, direction: "Xuất", status: "Hoàn thành", has_result: true, rows: [], result: { levels: { Fonds: { exported: 1, ancestors: 0 } } } }, levels: LEVELS } });
    expect(exported.find("a[href*='download?job=XJ-2026-00001']").exists()).toBe(true);
    expect(exported.text()).toContain("Đã xuất");
  });
});
