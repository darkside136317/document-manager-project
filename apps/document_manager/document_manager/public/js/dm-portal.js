// Document Manager Portal Shared Functions
(function () {
'use strict';

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


// ---------------------------------------------------------------------------
// Reader requests (Usage Request, Copy Request, Reader Feedback)
// State changes always go through the Workflow API; the server enforces roles.
// ---------------------------------------------------------------------------
const DM_API = 'document_manager.document_manager.api.requests.';

function dmErrorMessage(result) {
    let msg = 'Có lỗi xảy ra.';
    try {
        if (result._server_messages) {
            const msgs = JSON.parse(result._server_messages);
            if (msgs.length) msg = JSON.parse(msgs[msgs.length - 1]).message || msg;
        } else if (result.exception) {
            msg = String(result.exception).replace(/^[\w.]+: /, '');
        }
    } catch (e) { /* keep default */ }
    return msg;
}

window.dmServerMessage = function(body, fallback) {
    const msg = dmErrorMessage(body || {});
    return msg === 'Có lỗi xảy ra.' ? (fallback || msg) : msg;
};

/** POST a whitelisted method with a JSON body; resolves with `message`, rejects with Error(message). */
window.dmCall = async function(method, args) {
    const response = await fetch('/api/method/' + method, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-Frappe-CSRF-Token': frappe.csrf_token
        },
        body: JSON.stringify(args || {})
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(dmErrorMessage(body));
    return body.message;
};

function dmShowError(err) {
    frappe.msgprint({title: 'Lỗi', indicator: 'red', message: err.message || String(err)});
}

window.dmAddItemRow = function() {
    const body = document.getElementById('itemsBody');
    const withCopy = body.dataset.copyCount === '1';
    const tr = document.createElement('tr');
    tr.className = 'item-row';
    tr.innerHTML =
        '<td><input type="text" class="dm-form-control item-archival-file" list="dl-file"></td>' +
        '<td><input type="text" class="dm-form-control item-archive-document" list="dl-document"></td>' +
        (withCopy ? '<td><input type="number" min="1" class="dm-form-control item-copy-count" value="1"></td>' : '') +
        '<td><input type="text" class="dm-form-control item-notes"></td>' +
        '<td style="text-align:center"><button type="button" class="dm-btn danger" style="padding:6px 10px" ' +
        'onclick="this.closest(\'tr\').remove()"><i class="fa fa-trash"></i></button></td>';
    body.appendChild(tr);
};

window.dmSaveRequest = async function(submit) {
    const cfg = window.DM_REQUEST;
    const items = [];
    document.querySelectorAll('#itemsBody .item-row').forEach(row => {
        const archival_file = row.querySelector('.item-archival-file').value.trim();
        const archive_document = row.querySelector('.item-archive-document').value.trim();
        if (!archival_file && !archive_document) return;
        const item = {
            archival_file: archival_file,
            archive_document: archive_document,
            notes: row.querySelector('.item-notes').value.trim()
        };
        const copies = row.querySelector('.item-copy-count');
        if (copies) item.copy_count = parseInt(copies.value, 10) || 1;
        items.push(item);
    });
    if (!items.length) {
        return dmShowError(new Error('Vui lòng nhập ít nhất 1 hồ sơ hoặc văn bản'));
    }
    const payload = {purpose: document.getElementById('purpose').value, items: items};
    const reader = document.getElementById('reader');
    if (reader && reader.tagName === 'SELECT') {
        if (!reader.value) return dmShowError(new Error('Vui lòng chọn Độc giả'));
        payload.reader = reader.value;
    }
    const buttons = document.querySelectorAll('.dm-page-actions button');
    buttons.forEach(b => { b.disabled = true; });  // prevent double submit / duplicate drafts
    try {
        const res = await dmCall(DM_API + 'save_request', {
            doctype: cfg.doctype,
            payload: JSON.stringify(payload),
            name: document.getElementById('docname').value || null,
            submit: submit ? 1 : 0
        });
        window.location.href = cfg.route + '/form?name=' + encodeURIComponent(res.name);
    } catch (err) {
        buttons.forEach(b => { b.disabled = false; });
        dmShowError(err);
    }
};

window.dmRequestAction = async function(btn) {
    const cfg = window.DM_REQUEST;
    const action = btn.dataset.action;
    const textEl = document.getElementById('action_text');
    const notesEl = document.getElementById('action_notes');
    const text = textEl ? textEl.value.trim() : '';
    if (action === 'Từ chối' && !text) {
        return dmShowError(new Error('Vui lòng nhập lý do từ chối'));
    }
    if (action === 'Phản hồi' && !text) {
        return dmShowError(new Error('Vui lòng nhập nội dung phản hồi'));
    }
    if (action === 'Hủy phiếu' && !window.confirm('Hủy phiếu này?')) return;
    btn.disabled = true;
    try {
        await dmCall(DM_API + 'apply_action', {
            doctype: cfg.doctype,
            name: document.getElementById('docname').value,
            action: action,
            text: text || null,
            notes: notesEl ? notesEl.value.trim() || null : null
        });
        window.location.reload();
    } catch (err) {
        btn.disabled = false;
        dmShowError(err);
    }
};

window.dmSubmitFeedback = async function() {
    const subject = document.getElementById('subject').value.trim();
    const content = document.getElementById('content').value.trim();
    if (!subject || !content) {
        return dmShowError(new Error('Vui lòng nhập tiêu đề và nội dung'));
    }
    const buttons = document.querySelectorAll('.dm-page-actions button');
    buttons.forEach(b => { b.disabled = true; });
    try {
        const res = await dmCall(DM_API + 'submit_feedback', {subject: subject, content: content});
        window.location.href = window.DM_REQUEST.route + '/form?name=' + encodeURIComponent(res.name);
    } catch (err) {
        buttons.forEach(b => { b.disabled = false; });
        dmShowError(err);
    }
};

// Autocomplete for item pickers (server applies the reader's confidentiality limit).
const dmTimers = new WeakMap();

async function dmFillSuggestions(el) {
    const isFile = el.classList.contains('item-archival-file');
    const list = document.getElementById(isFile ? 'dl-file' : 'dl-document');
    if (!list) return;
    try {
        const r = await fetch('/api/method/' + DM_API + 'search_items?kind=' + (isFile ? 'file' : 'document') +
            '&txt=' + encodeURIComponent(el.value), {headers: {'Accept': 'application/json'}});
        const body = await r.json();
        list.innerHTML = '';
        (body.message || []).forEach(function(o) {
            const opt = document.createElement('option');
            opt.value = o.value;
            opt.label = o.label;
            list.appendChild(opt);
        });
    } catch (err) { /* autocomplete is best effort */ }
}

function dmIsPicker(el) {
    return el && el.classList && (el.classList.contains('item-archival-file') ||
                                  el.classList.contains('item-archive-document'));
}

document.addEventListener('input', function(e) {
    if (!dmIsPicker(e.target)) return;
    clearTimeout(dmTimers.get(e.target));
    dmTimers.set(e.target, setTimeout(function() { dmFillSuggestions(e.target); }, 250));
});
document.addEventListener('focusin', function(e) {
    if (dmIsPicker(e.target)) dmFillSuggestions(e.target);
});

// New request forms start with one empty item row.
function dmInitItemRows() {
    const body = document.getElementById('itemsBody');
    if (body && body.dataset.editable === '1' && !body.querySelector('.item-row')) window.dmAddItemRow();
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', dmInitItemRows);
else dmInitItemRows();
})();
