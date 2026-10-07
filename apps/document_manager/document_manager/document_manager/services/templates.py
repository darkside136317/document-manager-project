# -*- coding: utf-8 -*-
"""The forms the reader site and the printouts follow: the active Request Template of each kind.

When no template is active the built-in defaults apply (the reader site works on a bare site). Reading is
public on purpose: the registration form is shown to guests, so only the fields a guest may see are
returned — nothing here touches reader data.
"""

import frappe
from frappe.utils import cint
from frappe.utils.html_utils import clean_html

USAGE = "Phiếu yêu cầu sử dụng"
COPY = "Phiếu sao chụp"
REGISTRATION = "Đăng ký độc giả"
KIND_OF = {"Usage Request": USAGE, "Copy Request": COPY}

# field -> default label of the optional fields of the registration form
REGISTRATION_FIELDS = {
    "phone": "Điện thoại", "id_number": "Số CMND/CCCD", "organization": "Cơ quan, đơn vị",
    "position": "Chức vụ", "address": "Địa chỉ liên hệ", "purpose": "Mục đích khai thác tài liệu",
}
DEFAULT_PURPOSES = {
    USAGE: ["Nghiên cứu khoa học", "Phục vụ công tác chuyên môn", "Viết bài, xuất bản", "Giải quyết quyền lợi, thủ tục hành chính", "Mục đích khác"],
    COPY: ["Lưu hồ sơ cá nhân, cơ quan", "Phục vụ nghiên cứu", "Giải quyết quyền lợi, thủ tục hành chính", "Mục đích khác"],
}
DEFAULT_TITLES = {USAGE: "Phiếu yêu cầu sử dụng tài liệu", COPY: "Phiếu yêu cầu sao chụp tài liệu", REGISTRATION: "Đăng ký tài khoản độc giả"}


def _active(kind: str):
    name = frappe.db.get_value("Request Template", {"kind": kind, "is_active": 1}, "name")
    return frappe.get_doc("Request Template", name) if name else None


def slip_options(kind: str) -> frappe._dict:
    """Title, instructions, purposes and print texts of a slip form; `kind` is USAGE or COPY."""
    template = _active(kind)
    if not template:
        return frappe._dict(title=DEFAULT_TITLES[kind], instructions="", purposes=DEFAULT_PURPOSES[kind], require_purpose=True,
                            show_notes=True, print_header="", print_footer="", template=None)
    return frappe._dict(
        title=template.title or DEFAULT_TITLES[kind], instructions=clean_html(template.instructions or ""),
        purposes=[row.purpose.strip() for row in template.purposes if (row.purpose or "").strip()],
        require_purpose=bool(cint(template.require_purpose)), show_notes=bool(cint(template.show_notes)),
        print_header=template.print_header or "", print_footer=template.print_footer or "", template=template.name)


def slip_options_for(doctype: str) -> frappe._dict:
    return slip_options(KIND_OF[doctype])


def registration_form() -> frappe._dict:
    """`fields`: [{fieldname, label, visible, required}] of the optional registration fields, in a fixed order."""
    template = _active(REGISTRATION)
    configured = {row.field_name: row for row in (template.get("form_fields") if template else []) or []}
    fields = []
    for fieldname, default_label in REGISTRATION_FIELDS.items():
        row = configured.get(fieldname)
        visible = bool(cint(row.visible)) if row else True
        fields.append({"fieldname": fieldname, "label": (row.label if row and row.label else default_label),
                       "visible": visible, "required": bool(cint(row.required)) and visible if row else False})
    return frappe._dict(
        title=(template.title if template and template.title else DEFAULT_TITLES[REGISTRATION]),
        instructions=clean_html(template.instructions or "") if template else "", fields=fields)


def ensure_default_templates() -> int:
    """A site without templates gets one active template per kind, to edit instead of starting from nothing."""
    made = 0
    for kind in (USAGE, COPY, REGISTRATION):
        if frappe.db.exists("Request Template", {"kind": kind}):
            continue
        values = {"doctype": "Request Template", "template_name": f"Mẫu mặc định — {kind}", "kind": kind, "is_active": 1,
                  "title": DEFAULT_TITLES[kind], "require_purpose": 1, "show_notes": 1}
        if kind == REGISTRATION:
            values["form_fields"] = [{"field_name": f, "visible": 1, "required": 0} for f in REGISTRATION_FIELDS]
        else:
            values["purposes"] = [{"purpose": p} for p in DEFAULT_PURPOSES[kind]]
        frappe.get_doc(values).insert(ignore_permissions=True)
        made += 1
    return made


def dm_print_options(doctype: str) -> frappe._dict:
    """Title and header/footer text for the printouts of a slip (Jinja method `dm_print_options`)."""
    kind = KIND_OF.get(doctype)
    if not kind:
        return frappe._dict(title="", header="", footer="")
    options = slip_options(kind)
    return frappe._dict(title=options.title, header=options.print_header, footer=options.print_footer)
