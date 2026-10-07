/*
 * Reader site behaviour (Alpine.js components). Loaded before Alpine, which is vendored next to it.
 *
 * Nothing here decides who may see what: every call goes to a whitelisted method that checks the
 * session. The page only needs to be honest with the visitor (messages, disabled buttons).
 * `window.dm` exposes the helpers so they can be unit tested (frontend/tests/reader.test.js).
 */
(function () {
  "use strict";

  var BOOT = window.__DM__ || {};
  var API = "document_manager.document_manager.api";

  // ------------------------------------------------------------------ helpers
  // Page changes go through `nav` so tests can observe them (jsdom cannot navigate).
  var nav = {
    go: function (url) { window.location.assign(url); },
    reload: function () { window.location.reload(); },
  };

  function stripHtml(html) {
    return String(html == null ? "" : html)
      .replace(/<\s*br\s*\/?>/gi, "\n")
      .replace(/<\/(p|li|div)>/gi, "\n")
      .replace(/<[^>]+>/g, "")
      .replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
      .replace(/&quot;/g, '"').replace(/&#39;/g, "'")
      .replace(/\n{3,}/g, "\n\n").trim();
  }

  /** `_server_messages` is a JSON list of JSON strings: [{"message": "..."}]. */
  function serverMessages(payload) {
    var raw = payload && payload._server_messages;
    if (!raw) return [];
    try {
      return JSON.parse(raw).map(function (entry) {
        try { return stripHtml(JSON.parse(entry).message); } catch (e) { return stripHtml(entry); }
      }).filter(Boolean);
    } catch (e) {
      return [];
    }
  }

  function errorMessage(payload, status) {
    // the rate limiter's own text is English: the reader gets the Vietnamese one
    if (status === 429) return "Bạn thao tác quá nhanh. Vui lòng thử lại sau ít phút.";
    var messages = serverMessages(payload);
    if (messages.length) return messages.join("\n");
    if (status === 403) return "Bạn không có quyền thực hiện thao tác này.";
    if (status === 404) return "Không tìm thấy dữ liệu yêu cầu.";
    if (status >= 500) return "Máy chủ gặp lỗi. Vui lòng thử lại sau.";
    return "Không thực hiện được yêu cầu.";
  }

  function toQuery(args) {
    var params = new URLSearchParams();
    Object.keys(args).forEach(function (key) {
      var value = args[key];
      if (value === undefined || value === null || value === "") return;
      params.append(key, typeof value === "object" ? JSON.stringify(value) : String(value));
    });
    return params.toString();
  }

  function ApiError(message, status, payload) {
    var error = new Error(message);
    error.name = "ApiError";
    error.status = status || 0;
    error.payload = payload || {};
    return error;
  }

  function signIn() {
    var here = window.location.pathname + window.location.search;
    nav.go("/dang-nhap?redirect-to=" + encodeURIComponent(here));
  }

  /** Call a whitelisted method: GET with a query string, or POST (+ CSRF) when `post` is set. */
  function call(method, args, options) {
    args = args || {};
    options = options || {};
    var headers = { Accept: "application/json", "X-Frappe-CSRF-Token": BOOT.csrf || "" };
    var url = "/api/method/" + method;
    var init = { method: options.post ? "POST" : "GET", headers: headers, credentials: "same-origin" };
    if (options.post) {
      headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(args);
    } else {
      var query = toQuery(args);
      if (query) url += "?" + query;
    }
    return fetch(url, init).then(
      function (response) {
        return response.json().catch(function () { return {}; }).then(function (payload) {
          // An expired session sends the visitor to the sign-in page, except where a 401 is an answer
          // (wrong password) and the caller says so.
          if (options.signInOn401 !== false && (response.status === 401 ||
              (response.status === 403 && payload && payload.exc_type === "AuthenticationError"))) {
            signIn();
          }
          if (!response.ok) throw ApiError(errorMessage(payload, response.status), response.status, payload);
          return payload.message;
        });
      },
      function () { throw ApiError("Không kết nối được máy chủ. Kiểm tra mạng rồi thử lại."); }
    );
  }

  var api = {
    searchFiles: function (p) { return call(API + ".search.search_archival_files", p); },
    searchDocuments: function (p) { return call(API + ".search.search_documents", p); },
    addToBasket: function (kind, name, target) { return call(API + ".basket.add_to_basket", { kind: kind, name: name, target: target }, { post: true }); },
    removeFromBasket: function (doctype, name, row) { return call(API + ".basket.remove_from_basket", { doctype: doctype, name: name, row: row }, { post: true }); },
    discardDraft: function (doctype, name) { return call(API + ".basket.discard_draft", { doctype: doctype, name: name }, { post: true }); },
    saveRequest: function (doctype, payload, name, submit) { return call(API + ".requests.save_request", { doctype: doctype, payload: payload, name: name, submit: submit ? 1 : 0 }, { post: true }); },
    applyAction: function (doctype, name, action, text) { return call(API + ".requests.apply_action", { doctype: doctype, name: name, action: action, text: text }, { post: true }); },
    submitFeedback: function (subject, content) { return call(API + ".requests.submit_feedback", { subject: subject, content: content }, { post: true }); },
    register: function (form) { return call(API + ".registration.register_reader", form, { post: true }); },
    forgot: function (email, website) { return call(API + ".registration.request_password_reset", { email: email, website: website }, { post: true }); },
    updateProfile: function (form) { return call(API + ".account.update_profile", form, { post: true }); },
    changePassword: function (oldPassword, newPassword) { return call(API + ".account.change_password", { old_password: oldPassword, new_password: newPassword }, { post: true, signInOn401: false }); },
    markRead: function (names) { return call(API + ".account.mark_notifications_read", names ? { names: names } : {}, { post: true }); },
    setPassword: function (key, newPassword) { return call("frappe.core.doctype.user.user.update_password", { new_password: newPassword, key: key }, { post: true, signInOn401: false }); },
  };

  /** Only the <mark> tags the search engine adds survive; everything else is shown as text. */
  function safeHighlight(text) {
    var escaped = String(text == null ? "" : text)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    return escaped.replace(/&lt;mark&gt;/g, "<mark>").replace(/&lt;\/mark&gt;/g, "</mark>");
  }

  /** A redirect target is accepted only when it stays on this site. */
  function safeRedirect(path) {
    return typeof path === "string" && /^\/(?![\/\\])/.test(path) ? path : "";
  }

  function fmtDate(value) {
    var match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value || "");
    return match ? match[3] + "/" + match[2] + "/" + match[1] : value || "";
  }

  function theme() {
    var root = document.documentElement;
    return root.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }

  function setTheme(value) {
    document.documentElement.setAttribute("data-theme", value);
    try { localStorage.setItem("dm-theme", value); } catch (e) { /* the page works without remembering */ }
  }

  // ------------------------------------------------------------------ components
  var components = {};

  var SEARCH_FIELDS = {
    files: ["fonds", "file_number", "file_title", "confidentiality_level", "start_date_from", "start_date_to"],
    documents: ["fonds", "document_number", "document_title", "author", "file_type", "confidentiality_level", "date_from", "date_to"],
  };

  function blankFields() {
    var out = {};
    Object.keys(SEARCH_FIELDS).forEach(function (kind) {
      out[kind] = {};
      SEARCH_FIELDS[kind].forEach(function (field) { out[kind][field] = ""; });
    });
    return out;
  }

  components.searchPage = function (config) {
    config = config || {};
    return {
      kind: "files",
      q: "",
      adv: false,
      f: blankFields(),
      sort: "modified",
      page: 1,
      pageSize: 20,
      rows: [],
      total: 0,
      loading: false,
      error: "",
      searched: false,
      engine: "",
      fonds: config.fonds || {},
      canAdd: config.canAdd || { usage: false, copy: false },

      init: function () {
        var params = new URLSearchParams(window.location.search);
        this.kind = params.get("k") === "documents" ? "documents" : "files";
        this.q = params.get("q") || "";
        this.sort = params.get("sort") || "modified";
        this.page = Math.max(1, parseInt(params.get("page"), 10) || 1);
        var self = this;
        SEARCH_FIELDS[this.kind].forEach(function (field) { self.f[self.kind][field] = params.get(field) || ""; });
        this.adv = SEARCH_FIELDS[this.kind].some(function (field) { return self.f[self.kind][field]; });
        if (this.hasCriteria()) this.run();
      },

      hasCriteria: function () {
        var fields = this.f[this.kind] || {};
        return !!(this.q.trim() || Object.keys(fields).some(function (key) { return String(fields[key] || "").trim(); }));
      },

      params: function () {
        var out = { page: this.page, page_size: this.pageSize, sort_by: this.sort };
        if (this.q.trim()) out.query = this.q.trim();
        var fields = this.f[this.kind];
        Object.keys(fields).forEach(function (key) {
          var value = String(fields[key] || "").trim();
          if (value) out[key] = value;
        });
        return out;
      },

      pushUrl: function () {
        var params = this.params();
        var url = new URLSearchParams();
        url.set("k", this.kind);
        Object.keys(params).forEach(function (key) {
          if (key === "query") url.set("q", params[key]);
          else if (key === "sort_by") { if (params[key] !== "modified") url.set("sort", params[key]); }
          else if (key === "page") { if (params[key] > 1) url.set("page", params[key]); }
          else if (key !== "page_size") url.set(key, params[key]);
        });
        try { window.history.replaceState(null, "", window.location.pathname + "?" + url.toString()); } catch (e) { /* not essential */ }
      },

      submit: function () {
        this.page = 1;
        return this.run();
      },

      run: function () {
        var self = this;
        if (!this.hasCriteria()) {
          this.error = "Nhập từ khóa hoặc chọn ít nhất một điều kiện tìm kiếm.";
          return Promise.resolve();
        }
        this.loading = true;
        this.error = "";
        var request = this.kind === "files" ? api.searchFiles(this.params()) : api.searchDocuments(this.params());
        return request.then(function (result) {
          self.rows = result.data || [];
          self.total = result.total || 0;
          self.engine = result.engine || "";
          self.searched = true;
          self.pushUrl();
        }).catch(function (error) {
          self.rows = [];
          self.total = 0;
          self.error = error.message;
        }).then(function () { self.loading = false; });
      },

      setKind: function (kind) {
        if (kind === this.kind) return;
        this.kind = kind;
        this.page = 1;
        this.rows = [];
        this.total = 0;
        this.searched = false;
        this.adv = false;
        if (this.hasCriteria()) this.run();
      },

      reset: function () {
        var fields = this.f[this.kind];
        Object.keys(fields).forEach(function (key) { fields[key] = ""; });
        this.q = "";
        this.rows = [];
        this.total = 0;
        this.searched = false;
        this.error = "";
        this.page = 1;
        try { window.history.replaceState(null, "", window.location.pathname); } catch (e) { /* not essential */ }
      },

      get totalPages() { return Math.max(1, Math.ceil(this.total / this.pageSize)); },
      go: function (page) {
        page = Math.min(Math.max(1, page), this.totalPages);
        if (page === this.page) return;
        this.page = page;
        this.run();
        var top = document.getElementById("results");
        if (top && top.scrollIntoView) top.scrollIntoView({ behavior: "smooth", block: "start" });
      },
      get from() { return this.total ? (this.page - 1) * this.pageSize + 1 : 0; },
      get to() { return Math.min(this.total, this.page * this.pageSize); },

      id: function (row) { return row.name || row.id; },
      href: function (row) { return (this.kind === "files" ? "/portal/ho-so/" : "/portal/van-ban/") + encodeURIComponent(this.id(row)); },
      title: function (row) { return (this.kind === "files" ? row.file_title : row.document_title) || this.id(row); },
      titleHtml: function (row) {
        var marked = row._formatted && row._formatted.document_title;
        return safeHighlight(this.kind === "documents" && marked ? marked : this.title(row));
      },
      snippet: function (row) { return row._formatted && row._formatted.content_text ? safeHighlight(row._formatted.content_text) : ""; },
      fondsLabel: function (row) { return this.fonds[row.fonds] || row.fonds || ""; },
      date: fmtDate,
      period: function (row) {
        var from = fmtDate(row.start_date), to = fmtDate(row.end_date);
        return from && to && from !== to ? from + " – " + to : from || to;
      },
      add: function (row, target) {
        return Alpine.store("basket").add(this.kind === "files" ? "file" : "document", this.id(row), target);
      },
    };
  };

  components.loginForm = function (config) {
    config = config || {};
    return {
      usr: "", pwd: "", show: false, busy: false, error: "",
      submit: function () {
        var self = this;
        if (!this.usr.trim() || !this.pwd) {
          this.error = "Vui lòng nhập email và mật khẩu.";
          return Promise.resolve();
        }
        this.busy = true;
        this.error = "";
        return fetch("/api/method/login", {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({ usr: this.usr.trim(), pwd: this.pwd }),
        }).then(function (response) {
          return response.json().catch(function () { return {}; }).then(function (payload) {
            if (response.status === 429) throw new Error("Bạn đăng nhập sai quá nhiều lần. Vui lòng thử lại sau ít phút.");
            if (!response.ok) throw new Error("Email hoặc mật khẩu không đúng, hoặc tài khoản đã bị khóa.");
            var home = payload.home_page ? String(payload.home_page) : "";
            if (home && home.charAt(0) !== "/") home = "/" + home;
            nav.go(safeRedirect(config.redirect) || safeRedirect(home) || "/portal");
          });
        }).catch(function (error) {
          self.error = error.message === "Failed to fetch" ? "Không kết nối được máy chủ." : error.message;
          self.busy = false;
        });
      },
    };
  };

  /** One component for the three guest forms; `submitFn(values)` returns the API promise. */
  function guestForm(extra) {
    return Object.assign({
      busy: false, error: "", done: false, result: null, website: "",
      run: function (promise) {
        var self = this;
        this.busy = true;
        this.error = "";
        return promise.then(function (result) {
          self.result = result;
          self.done = true;
        }).catch(function (error) {
          self.error = error.message;
        }).then(function () { self.busy = false; });
      },
    }, extra);
  }

  components.registerForm = function (config) {
    config = config || {};
    return guestForm({
      v: { full_name: "", email: "", phone: "", id_number: "", organization: "", position: "", address: "", purpose: "" },
      required: config.required || {}, // field -> label, from the registration template
      submit: function () {
        if (!this.v.full_name.trim() || !this.v.email.trim()) {
          this.error = "Vui lòng nhập họ tên và email.";
          return Promise.resolve();
        }
        var self = this;
        var missing = Object.keys(this.required).filter(function (field) { return !String(self.v[field] || "").trim(); });
        if (missing.length) {
          this.error = "Vui lòng nhập " + this.required[missing[0]].toLowerCase() + ".";
          return Promise.resolve();
        }
        return this.run(api.register(Object.assign({ website: this.website }, this.v)));
      },
    });
  };

  components.forgotForm = function () {
    return guestForm({
      email: "",
      submit: function () {
        if (!this.email.trim()) {
          this.error = "Vui lòng nhập email đã đăng ký.";
          return Promise.resolve();
        }
        return this.run(api.forgot(this.email.trim(), this.website));
      },
    });
  };

  components.setPasswordForm = function (config) {
    return {
      pwd: "", again: "", show: false, busy: false, error: "",
      submit: function () {
        var self = this;
        if (this.pwd.length < 8) { this.error = "Mật khẩu cần có ít nhất 8 ký tự."; return Promise.resolve(); }
        if (this.pwd !== this.again) { this.error = "Hai mật khẩu nhập vào không khớp."; return Promise.resolve(); }
        this.busy = true;
        this.error = "";
        return api.setPassword(config.key, this.pwd).then(function (target) {
          nav.go(safeRedirect(target) || "/portal");
        }).catch(function (error) {
          self.error = error.status === 410
            ? "Liên kết đã hết hạn hoặc đã được dùng. Hãy gửi yêu cầu cấp lại mật khẩu hoặc liên hệ cán bộ."
            : error.message;
          self.busy = false;
        });
      },
    };
  };

  components.slipEditor = function (config) {
    return {
      doctype: config.doctype,
      name: config.name,
      purpose: config.purpose || "",
      notes: config.notes || "",
      items: config.items || [],
      listUrl: config.listUrl,
      busy: false,
      error: "",
      payload: function () {
        return JSON.stringify({
          purpose: this.purpose, notes: this.notes,
          items: this.items.map(function (item) {
            return { archival_file: item.archival_file, archive_document: item.archive_document, notes: item.notes, copy_count: item.copy_count };
          }),
        });
      },
      work: function (promise, done) {
        var self = this;
        this.busy = true;
        this.error = "";
        return promise.then(done).catch(function (error) {
          self.error = error.message;
          self.busy = false;
        });
      },
      save: function () {
        var self = this;
        return this.work(api.saveRequest(this.doctype, this.payload(), this.name, false), function () {
          self.busy = false;
          Alpine.store("toast").show("Đã lưu phiếu.");
        });
      },
      send: function () {
        if (config.requirePurpose !== false && !this.purpose.trim()) { this.error = "Vui lòng nhập mục đích trước khi gửi."; return Promise.resolve(); }
        if (!this.items.length) { this.error = "Phiếu chưa có hồ sơ, văn bản nào."; return Promise.resolve(); }
        return this.work(api.saveRequest(this.doctype, this.payload(), this.name, true), function () { nav.reload(); });
      },
      removeItem: function (item) {
        var self = this;
        return this.work(api.removeFromBasket(this.doctype, this.name, item.row), function (result) {
          Alpine.store("basket").sync(config.target, result);
          if (!result.request) { nav.go(self.listUrl); return; }
          self.items = self.items.filter(function (x) { return x.row !== item.row; });
          self.busy = false;
        });
      },
      discard: function () {
        var self = this;
        if (!window.confirm("Hủy bản nháp này? Các hồ sơ, văn bản trong phiếu sẽ bị bỏ.")) return Promise.resolve();
        return this.work(api.discardDraft(this.doctype, this.name), function () {
          Alpine.store("basket").sync(config.target, { request: null, count: 0 });
          nav.go(self.listUrl);
        });
      },
      cancelSlip: function () {
        if (!window.confirm("Hủy phiếu này?")) return Promise.resolve();
        return this.work(api.applyAction(this.doctype, this.name, "Hủy phiếu"), function () { nav.reload(); });
      },
    };
  };

  components.feedbackForm = function () {
    return {
      subject: "", content: "", busy: false, error: "",
      submit: function () {
        var self = this;
        if (!this.subject.trim() || !this.content.trim()) { this.error = "Vui lòng nhập tiêu đề và nội dung góp ý."; return Promise.resolve(); }
        this.busy = true;
        this.error = "";
        return api.submitFeedback(this.subject.trim(), this.content.trim()).then(function () {
          nav.go("/portal/gop-y");
        }).catch(function (error) { self.error = error.message; self.busy = false; });
      },
    };
  };

  components.accountPage = function (config) {
    return {
      p: Object.assign({ phone: "", address: "", organization: "", position: "" }, config.profile || {}),
      saving: false, profileError: "", profileOk: false,
      old: "", next: "", again: "", changing: false, passError: "", passOk: false,
      saveProfile: function () {
        var self = this;
        this.saving = true;
        this.profileError = "";
        this.profileOk = false;
        return api.updateProfile({ phone: this.p.phone, address: this.p.address, organization: this.p.organization, position: this.p.position })
          .then(function () { self.profileOk = true; })
          .catch(function (error) { self.profileError = error.message; })
          .then(function () { self.saving = false; });
      },
      changePassword: function () {
        var self = this;
        this.passError = "";
        this.passOk = false;
        if (this.next.length < 8) { this.passError = "Mật khẩu mới cần có ít nhất 8 ký tự."; return Promise.resolve(); }
        if (this.next !== this.again) { this.passError = "Hai mật khẩu mới không khớp."; return Promise.resolve(); }
        this.changing = true;
        return api.changePassword(this.old, this.next).then(function () {
          self.passOk = true;
          self.old = self.next = self.again = "";
        }).catch(function (error) {
          self.passError = error.message;
        }).then(function () { self.changing = false; });
      },
    };
  };

  components.notificationsPage = function (config) {
    return {
      unread: config.unread || 0,
      read: {},
      markAll: function () {
        var self = this;
        return api.markRead().then(function (left) {
          self.unread = left;
          Alpine.store("notes").unread = left;
          document.querySelectorAll("[data-note]").forEach(function (el) { el.classList.remove("unread"); });
        }).catch(function (error) { Alpine.store("toast").show(error.message, { error: true }); });
      },
      open: function (name) {
        // Fire and forget: the link is followed regardless.
        api.markRead([name]).catch(function () { /* the bell catches up on the next page */ });
      },
    };
  };

  // ------------------------------------------------------------------ stores and registration
  document.addEventListener("alpine:init", function () {
    Object.keys(components).forEach(function (name) { Alpine.data(name, components[name]); });

    Alpine.store("toast", {
      items: [],
      show: function (message, options) {
        options = options || {};
        var item = { id: Date.now() + Math.random(), message: message, error: !!options.error, link: options.link || "", label: options.label || "" };
        this.items.push(item);
        var self = this;
        setTimeout(function () { self.items = self.items.filter(function (x) { return x.id !== item.id; }); }, options.error ? 7000 : 4500);
      },
    });

    var basket = BOOT.basket || {};
    Alpine.store("basket", {
      usage: basket.usage || { count: 0, name: null, route: "/portal/phieu" },
      copy: basket.copy || { count: 0, name: null, route: "/portal/sao-chep" },
      busy: false,
      get total() { return (this.usage.count || 0) + (this.copy.count || 0); },
      sync: function (target, result) {
        var slot = this[target];
        slot.count = result.count || 0;
        slot.name = result.request || null;
      },
      add: function (kind, name, target) {
        var self = this;
        this.busy = true;
        return api.addToBasket(kind, name, target).then(function (result) {
          self.sync(target, result);
          Alpine.store("toast").show(result.message, { link: result.route, label: "Mở phiếu" });
        }).catch(function (error) {
          Alpine.store("toast").show(error.message, { error: true });
        }).then(function () { self.busy = false; });
      },
    });

    Alpine.store("notes", { unread: BOOT.unread || 0 });
    Alpine.store("theme", {
      value: theme(),
      toggle: function () { this.value = this.value === "dark" ? "light" : "dark"; setTheme(this.value); },
    });
  });

  function signOut() {
    return fetch("/api/method/logout", { method: "POST", headers: { "X-Frappe-CSRF-Token": BOOT.csrf || "" }, credentials: "same-origin" })
      .catch(function () { /* the session ends with the cookie anyway */ })
      .then(function () { nav.go("/dang-nhap"); });
  }

  window.dm = {
    boot: BOOT, nav: nav, call: call, signOut: signOut, api: api, components: components, stripHtml: stripHtml, serverMessages: serverMessages,
    errorMessage: errorMessage, safeHighlight: safeHighlight, safeRedirect: safeRedirect, fmtDate: fmtDate,
  };
})();
