(function () {
    function escapeHTML(value) {
        return String(value == null ? "" : value).replace(/[&<>"']/g, function (character) {
            return {"&":"&amp;", "<":"&lt;", ">":"&gt;", "\"":"&quot;", "'":"&#039;"}[character];
        });
    }

    function formatNumber(value) {
        return Number(value || 0).toLocaleString("vi-VN");
    }

    function formatRelativeDate(value) {
        if (!value) return "";
        const date = new Date(String(value).replace(" ", "T"));
        if (Number.isNaN(date.getTime())) return "";
        return date.toLocaleDateString("vi-VN", {day: "2-digit", month: "2-digit", year: "numeric"});
    }

    function renderRecent(root, documents) {
        const target = root.querySelector("[data-dm-recent]");
        if (!documents || !documents.length) {
            target.innerHTML = '<div class="dm-dashboard-empty"><i class="fa fa-inbox"></i><span>Chưa có tài liệu gần đây</span></div>';
            return;
        }

        target.innerHTML = documents.map(function (doc) {
            const fileType = escapeHTML(doc.file_type || "Tệp");
            const statusClass = doc.search_index_status === "Đã index" ? "is-ready" : "is-pending";
            return '<a class="dm-dashboard-recent-item" href="/app/archive-document/' + encodeURIComponent(doc.name) + '">' +
                '<span class="dm-dashboard-filetype">' + fileType + '</span>' +
                '<span class="dm-dashboard-recent-item__main"><strong>' + escapeHTML(doc.document_title || doc.name) +
                '</strong><small>' + escapeHTML(doc.name) + ' · ' + formatRelativeDate(doc.modified) + '</small></span>' +
                '<span class="dm-dashboard-index-state ' + statusClass + '"><i class="fa fa-circle"></i>' +
                escapeHTML(doc.search_index_status || "Chưa index") + '</span></a>';
        }).join("");
    }

    function init(root) {
        if (!root || root.dataset.dmDashboardReady === "1") return;
        root.dataset.dmDashboardReady = "1";

        const user = frappe.session.user_fullname || frappe.session.user || "Người dùng";
        const userNode = root.querySelector("[data-dm-user]");
        const dateNode = root.querySelector("[data-dm-date]");
        if (userNode) userNode.textContent = user;
        if (dateNode) {
            dateNode.textContent = new Date().toLocaleDateString("vi-VN", {
                weekday: "long", day: "2-digit", month: "2-digit", year: "numeric"
            });
        }

        const createButton = root.querySelector("[data-dm-new-document]");
        if (createButton) {
            createButton.addEventListener("click", function () {
                frappe.new_doc("Archive Document");
            });
        }

        frappe.call({
            method: "document_manager.document_manager.api.dashboard.get_workspace_summary",
            callback: function (response) {
                const data = response.message || {};
                root.querySelectorAll("[data-dm-stat]").forEach(function (node) {
                    node.textContent = formatNumber(data[node.dataset.dmStat]);
                });

                const percent = Math.max(0, Math.min(100, Number(data.index_percent || 0)));
                const bar = root.querySelector("[data-dm-index-bar]");
                const label = root.querySelector("[data-dm-index-label]");
                if (bar) bar.style.width = percent + "%";
                if (label) label.textContent = percent + "%";
                renderRecent(root, data.recent_documents || []);
            },
            error: function () {
                const target = root.querySelector("[data-dm-recent]");
                if (target) {
                    target.innerHTML = '<div class="dm-dashboard-empty"><i class="fa fa-exclamation-circle"></i><span>Chưa thể tải dữ liệu tổng quan</span></div>';
                }
            }
        });
    }

    window.DocumentManagerDashboard = {init: init};
})();
