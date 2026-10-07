// Upload of document files: validation, one XHR per file (fetch cannot report upload progress), and
// a small queue that turns each uploaded file into a document of an archival file.
import { ApiError, errorMessage, serverMessages } from "./api.js";
import { csrfToken } from "./boot.js";

export const extensionOf = (name) => {
  const dot = String(name || "").lastIndexOf(".");
  return dot < 0 ? "" : name.slice(dot + 1).toLowerCase();
};

export function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/** The reason a file cannot be uploaded, or "" when it can. `rules` = {extensions, max_mb}. */
export function validateFile(file, rules) {
  const extension = extensionOf(file.name);
  if (!rules.extensions.includes(extension)) {
    return `Định dạng .${extension || "?"} không được hỗ trợ (chấp nhận: ${rules.extensions.join(", ")})`;
  }
  if (file.size > rules.max_mb * 1024 * 1024) return `Tệp lớn hơn ${rules.max_mb} MB (${formatSize(file.size)})`;
  if (file.size === 0) return "Tệp rỗng";
  return "";
}

/** POST one file to Frappe's upload_file as a private file. Resolves with the File record. */
export function uploadFile(file, { onProgress = () => {}, xhrFactory = () => new XMLHttpRequest() } = {}) {
  return new Promise((resolve, reject) => {
    const xhr = xhrFactory();
    xhr.open("POST", "/api/method/upload_file");
    xhr.setRequestHeader("X-Frappe-CSRF-Token", csrfToken());
    xhr.setRequestHeader("Accept", "application/json");
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onerror = () => reject(new ApiError("Mất kết nối khi tải tệp lên"));
    xhr.onabort = () => reject(new ApiError("Đã hủy tải tệp"));
    xhr.onload = () => {
      let payload = {};
      try {
        payload = JSON.parse(xhr.responseText || "{}");
      } catch {
        /* an HTML error page: reported by status below */
      }
      if (xhr.status >= 200 && xhr.status < 300 && payload.message?.file_url) return resolve(payload.message);
      reject(new ApiError(errorMessage(payload, xhr.status), { status: xhr.status, messages: serverMessages(payload) }));
    };
    const form = new FormData();
    form.append("file", file, file.name);
    form.append("is_private", "1");
    form.append("folder", "Home/Attachments");
    xhr.send(form);
  });
}

/**
 * Upload `items` (reactive {file, status, progress, error, document}) one after another, at most
 * `concurrency` at a time, and make a document of each. `create(fileUrl, file)` does the last step.
 */
export async function processQueue(items, { rules, create, concurrency = 2, upload = uploadFile }) {
  const pending = items.filter((item) => item.status === "waiting");
  let next = 0;
  // Uploads overlap, but documents are created one by one: parallel inserts fight over the next number.
  let creating = Promise.resolve();
  const createInTurn = (fileUrl, file) => {
    const turn = creating.then(() => create(fileUrl, file));
    creating = turn.catch(() => {});
    return turn;
  };

  async function worker() {
    while (next < pending.length) {
      const item = pending[next++];
      const problem = validateFile(item.file, rules);
      if (problem) {
        Object.assign(item, { status: "error", error: problem });
        continue;
      }
      try {
        item.status = "uploading";
        item.progress = 0;
        const stored = await upload(item.file, { onProgress: (percent) => (item.progress = percent) });
        item.status = "saving";
        item.document = await createInTurn(stored.file_url, item.file);
        Object.assign(item, { status: "done", progress: 100 });
      } catch (error) {
        Object.assign(item, { status: "error", error: error.message || "Không tải lên được" });
      }
    }
  }
  await Promise.all(Array.from({ length: Math.min(concurrency, pending.length) }, worker));
  return items;
}
