import { describe, expect, it, vi } from "vitest";
import { extensionOf, formatSize, processQueue, uploadFile, validateFile } from "../src/lib/upload.js";
import { reactive } from "vue";

const rules = { extensions: ["pdf", "docx", "jpg"], max_mb: 1 };
const file = (name, size = 1000) => ({ name, size });
const real = (name) => new File(["content"], name); // FormData wants a real Blob

describe("validation", () => {
  it("reads extensions case-insensitively", () => {
    expect(extensionOf("Báo cáo.PDF")).toBe("pdf");
    expect(extensionOf("archive.tar.gz")).toBe("gz");
    expect(extensionOf("noext")).toBe("");
  });
  it("accepts an allowed type within the limit", () => {
    expect(validateFile(file("a.pdf"), rules)).toBe("");
    expect(validateFile(file("A.JPG", 1024 * 1024), rules)).toBe("");
  });
  it("explains each refusal", () => {
    expect(validateFile(file("virus.exe"), rules)).toMatch(/\.exe không được hỗ trợ/);
    expect(validateFile(file("noext"), rules)).toMatch(/không được hỗ trợ/);
    expect(validateFile(file("big.pdf", 1024 * 1024 + 1), rules)).toMatch(/lớn hơn 1 MB/);
    expect(validateFile(file("empty.pdf", 0), rules)).toBe("Tệp rỗng");
  });
  it("formats sizes", () => {
    expect(formatSize(512)).toBe("512 B");
    expect(formatSize(2048)).toBe("2 KB");
    expect(formatSize(5 * 1024 * 1024)).toBe("5.0 MB");
  });
});

function fakeXhr() {
  const xhr = {
    headers: {},
    upload: {},
    open: vi.fn((method, url) => Object.assign(xhr, { method, url })),
    setRequestHeader: vi.fn((k, v) => (xhr.headers[k] = v)),
    send: vi.fn((body) => (xhr.body = body)),
    status: 200,
    responseText: "",
  };
  return xhr;
}

describe("uploadFile", () => {
  it("posts the file privately with the CSRF header and reports progress", async () => {
    const xhr = fakeXhr();
    const progress = vi.fn();
    const promise = uploadFile(real("a.pdf"), { onProgress: progress, xhrFactory: () => xhr });
    xhr.upload.onprogress({ lengthComputable: true, loaded: 25, total: 100 });
    xhr.upload.onprogress({ lengthComputable: false, loaded: 0, total: 0 });
    xhr.responseText = JSON.stringify({ message: { name: "f1", file_url: "/private/files/a.pdf" } });
    xhr.onload();
    await expect(promise).resolves.toEqual({ name: "f1", file_url: "/private/files/a.pdf" });
    expect(xhr.url).toBe("/api/method/upload_file");
    expect(xhr.headers).toHaveProperty("X-Frappe-CSRF-Token");
    expect(progress).toHaveBeenCalledTimes(1);
    expect(progress).toHaveBeenCalledWith(25);
    expect(xhr.body.get("is_private")).toBe("1");
  });

  it("turns a server refusal into a readable error", async () => {
    const xhr = fakeXhr();
    const promise = uploadFile(real("a.pdf"), { xhrFactory: () => xhr });
    xhr.status = 417;
    xhr.responseText = JSON.stringify({ _server_messages: JSON.stringify([JSON.stringify({ message: "File size exceeded the maximum allowed size" })]) });
    xhr.onload();
    await expect(promise).rejects.toThrow("File size exceeded the maximum allowed size");
  });

  it("copes with an HTML error page and with a dropped connection", async () => {
    const html = fakeXhr();
    const first = uploadFile(real("a.pdf"), { xhrFactory: () => html });
    html.status = 413;
    html.responseText = "<html>413 Request Entity Too Large</html>";
    html.onload();
    await expect(first).rejects.toThrow();
    const dead = fakeXhr();
    const second = uploadFile(real("a.pdf"), { xhrFactory: () => dead });
    dead.onerror();
    await expect(second).rejects.toThrow(/Mất kết nối/);
  });
});

const item = (name, size = 1000) => reactive({ file: file(name, size), status: "waiting", progress: 0, error: "", document: null });

describe("processQueue", () => {
  it("uploads every valid file, makes a document of each and leaves the invalid ones with their reason", async () => {
    const items = [item("a.pdf"), item("b.exe"), item("c.docx")];
    const upload = vi.fn(async (f, { onProgress }) => { onProgress(60); return { file_url: `/private/files/${f.name}` }; });
    const create = vi.fn(async (url) => ({ name: `DOC-${url.split("/").pop()}` }));
    await processQueue(items, { rules, create, upload });
    expect(items.map((i) => i.status)).toEqual(["done", "error", "done"]);
    expect(items[1].error).toMatch(/\.exe/);
    expect(items[0].document.name).toBe("DOC-a.pdf");
    expect(items[0].progress).toBe(100);
    expect(upload).toHaveBeenCalledTimes(2);
    expect(create).toHaveBeenCalledTimes(2);
  });

  it("keeps going after a failure and reports the message", async () => {
    const items = [item("a.pdf"), item("b.pdf"), item("c.pdf")];
    const upload = async (f) => ({ file_url: `/${f.name}` });
    const create = async (url) => { if (url === "/b.pdf") throw new Error("Hồ sơ không tồn tại"); return { name: url }; };
    await processQueue(items, { rules, create, upload });
    expect(items.map((i) => i.status)).toEqual(["done", "error", "done"]);
    expect(items[1].error).toBe("Hồ sơ không tồn tại");
  });

  it("never runs more uploads at once than allowed", async () => {
    const items = Array.from({ length: 6 }, (_, n) => item(`f${n}.pdf`));
    let running = 0;
    let peak = 0;
    const upload = async (f) => {
      running += 1;
      peak = Math.max(peak, running);
      await new Promise((resolve) => setTimeout(resolve, 5));
      running -= 1;
      return { file_url: `/${f.name}` };
    };
    await processQueue(items, { rules, create: async (u) => ({ name: u }), upload, concurrency: 2 });
    expect(peak).toBe(2);
    expect(items.every((i) => i.status === "done")).toBe(true);
  });

  it("skips items that are not waiting (already done or failed)", async () => {
    const done = item("a.pdf");
    done.status = "done";
    const upload = vi.fn(async () => ({ file_url: "/x" }));
    await processQueue([done], { rules, create: async () => ({}), upload });
    expect(upload).not.toHaveBeenCalled();
  });
});

describe("document creation order", () => {
  it("creates documents one at a time even though uploads overlap", async () => {
    const items = Array.from({ length: 5 }, (_, n) => item(`f${n}.pdf`));
    let creating = 0;
    let peak = 0;
    const order = [];
    const create = async (url) => {
      creating += 1;
      peak = Math.max(peak, creating);
      await new Promise((resolve) => setTimeout(resolve, 4));
      creating -= 1;
      order.push(url);
      return { name: url };
    };
    await processQueue(items, { rules, create, upload: async (f) => ({ file_url: `/${f.name}` }), concurrency: 3 });
    expect(peak).toBe(1);
    expect(items.every((i) => i.status === "done")).toBe(true);
    expect(order).toHaveLength(5);
  });

  it("a failing creation does not block the ones queued behind it", async () => {
    const items = [item("a.pdf"), item("b.pdf"), item("c.pdf")];
    const create = async (url) => { if (url === "/a.pdf") throw new Error("lỗi"); return { name: url }; };
    await processQueue(items, { rules, create, upload: async (f) => ({ file_url: `/${f.name}` }), concurrency: 3 });
    expect(items.map((i) => i.status)).toEqual(["error", "done", "done"]);
  });
});
