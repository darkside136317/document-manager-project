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

        root.querySelectorAll("[data-dm-new-doctype]").forEach(function (link) {
            link.addEventListener("click", function (event) {
                event.preventDefault();
                frappe.new_doc(link.dataset.dmNewDoctype);
            });
        });

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

    // Inject into Frappe Workspace automatically
    function injectDashboardIntoWorkspace() {
        const route = frappe.get_route();
        const route0 = route[0] ? route[0].toLowerCase() : "";
        if (( (route0 === "workspace" || route0 === "workspaces") && route[1] === "Document Manager") || route0 === "document-manager") {
            let attempts = 0;
            const checkExist = setInterval(function() {
                const container = document.querySelector(".workspace-page .layout-main-section") || document.querySelector(".layout-main-section");
                
                // If container is found and Vue has rendered the standard blocks
                if (container && container.children.length > 0) {
                    clearInterval(checkExist);
                    if (!container.querySelector(".dm-workspace-container")) {
                        frappe.db.get_value("Custom HTML Block", "Document Manager Overview", ["html", "style"])
                            .then(r => {
                                if (r && r.message) {
                                    // Hide all standard blocks
                                    Array.from(container.children).forEach(c => {
                                        c.style.display = "none";
                                    });
                                    
                                    const wrapper = document.createElement("div");
                                    wrapper.className = "dm-workspace-container";
                                    wrapper.innerHTML = "<style>" + (r.message.style || "") + "</style>" + (r.message.html || "");
                                    container.appendChild(wrapper);
                                    
                                    init(wrapper);
                                }
                            });
                    }
                }
                
                attempts++;
                if (attempts > 20) {
                    clearInterval(checkExist); // Stop checking after 10 seconds
                }
            }, 500); // Check every 500ms
        }
    }

    if (window.frappe) {
        if (frappe.router) {
            frappe.router.on("change", injectDashboardIntoWorkspace);
        }
        $(document).on("page-change", injectDashboardIntoWorkspace);
        // Run once on load
        setTimeout(injectDashboardIntoWorkspace, 500);
    }
})();
