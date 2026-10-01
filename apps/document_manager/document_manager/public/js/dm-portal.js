// Document Manager Portal Shared Functions

frappe.ready(function() {
    /**
     * Common helper to save a DocType record via Frappe REST API.
     * 
     * @param {string} doctype - The name of the DocType (e.g. "Archive Document").
     * @param {string} docname - The existing document name if editing, or empty if creating.
     * @param {object} data - The payload data to save.
     * @param {string} redirectBaseUrl - The base URL to redirect to upon success (e.g. "/archive_documents/form").
     * @param {HTMLElement} btnElement - (Optional) The button element to disable during save.
     */
    window.dmSaveRecord = async function(doctype, docname, data, redirectBaseUrl, btnElement = null) {
        if (!doctype || !data) {
            console.error("dmSaveRecord requires 'doctype' and 'data' parameters.");
            return;
        }

        if (btnElement) {
            btnElement.disabled = true;
            const originalText = btnElement.innerHTML;
            btnElement.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Đang lưu...';
            btnElement.dataset.originalText = originalText;
        }

        try {
            let url = '/api/resource/' + encodeURIComponent(doctype);
            let method = 'POST';
            
            if (docname) {
                url += '/' + encodeURIComponent(docname);
                method = 'PUT';
            }
            
            const response = await fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                    'X-Frappe-CSRF-Token': frappe.csrf_token
                },
                body: JSON.stringify(data)
            });
            
            const result = await response.json();
            
            if (response.ok) {
                frappe.msgprint({title: 'Thành công', indicator: 'green', message: 'Đã lưu thông tin thành công!'});
                if (redirectBaseUrl) {
                    const savedDocname = result.data ? result.data.name : docname;
                    const separator = redirectBaseUrl.includes('?') ? '&' : '?';
                    setTimeout(() => {
                        window.location.href = redirectBaseUrl + separator + 'name=' + savedDocname;
                    }, 1000);
                }
            } else {
                let errMsg = 'Có lỗi xảy ra trong quá trình lưu dữ liệu.';
                if (result._server_messages) {
                    try {
                        const msgs = JSON.parse(result._server_messages);
                        if (msgs && msgs.length > 0) {
                            errMsg = JSON.parse(msgs[0]).message || errMsg;
                        }
                    } catch(e) {
                        console.error("Failed to parse _server_messages:", e);
                    }
                }
                frappe.msgprint({title: 'Lỗi', indicator: 'red', message: errMsg});
            }
        } catch (error) {
            frappe.msgprint({title: 'Lỗi', indicator: 'red', message: 'Không thể kết nối đến máy chủ. Vui lòng thử lại sau.'});
            console.error("API Error:", error);
        } finally {
            if (btnElement) {
                btnElement.disabled = false;
                btnElement.innerHTML = btnElement.dataset.originalText;
            }
        }
    };
});
