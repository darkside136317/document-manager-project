// Document Manager Portal Shared Functions

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
                'X-Frappe-CSRF-Token': typeof frappe !== 'undefined' ? frappe.csrf_token : ''
            },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            if (typeof frappe !== 'undefined' && frappe.msgprint) {
                frappe.msgprint({title: 'Thành công', indicator: 'green', message: 'Đã lưu thông tin thành công!'});
            } else {
                alert('Đã lưu thông tin thành công!');
            }
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
            } else if (result.exc) {
                // For TimestampMismatchError or generic backend exceptions
                const excArr = JSON.parse(result.exc || '[]');
                if (excArr.length) {
                     const match = excArr[0].match(/frappe\.exceptions\.\w+: (.*)/);
                     if (match) errMsg = match[1];
                     else errMsg = "Lỗi hệ thống hoặc sai mốc thời gian lưu (Timestamp Mismatch).";
                }
            }
            if (typeof frappe !== 'undefined' && frappe.msgprint) {
                frappe.msgprint({title: 'Lỗi', indicator: 'red', message: errMsg});
            } else {
                alert('Lỗi: ' + errMsg);
            }
        }
    } catch (error) {
        if (typeof frappe !== 'undefined' && frappe.msgprint) {
            frappe.msgprint({title: 'Lỗi', indicator: 'red', message: 'Không thể kết nối đến máy chủ. Vui lòng thử lại sau.'});
        } else {
            alert('Lỗi: Không thể kết nối đến máy chủ.');
        }
        console.error("API Error:", error);
    } finally {
        if (btnElement) {
            btnElement.disabled = false;
            btnElement.innerHTML = btnElement.dataset.originalText;
        }
    }
};
