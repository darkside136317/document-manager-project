# -*- coding: utf-8 -*-
"""What the public pages (/gioi-thieu, /lanh-dao, /co-cau, /lien-he, /huong-dan) may tell a guest.

Organization Info is readable by readers and staff only, so guests get a *curated* copy built here:
hidden leaders and units are left out, rich text is sanitised, and only http(s) or site-relative
links are kept. Nothing in this module reads reader data.
"""

import frappe
from frappe.utils import cint
from frappe.utils.html_utils import clean_html

DEFAULT_ORG_NAME = "Trung tâm Lưu trữ"
DEFAULT_TAGLINE = "Tra cứu, khai thác hồ sơ và tài liệu lưu trữ trực tuyến"


def _safe_url(value) -> str:
    """Links and image paths entered in a form may only be http(s) or site-relative."""
    value = (value or "").strip()
    if value.startswith("/") and not value.startswith("//"):
        return value
    return value if value.lower().startswith(("http://", "https://")) else ""


def _lines(value) -> list[str]:
    return [line.strip() for line in (value or "").splitlines() if line.strip()]


def get_org_profile() -> dict:
    """The unit's public profile. Always returns a usable dict, even when nothing is filled in yet."""
    info = frappe.get_cached_doc("Organization Info")
    leaders = sorted((row for row in info.get("leaders") or [] if cint(row.is_visible)),
                     key=lambda row: (cint(row.display_order), row.idx))
    return {
        "name": info.org_name or DEFAULT_ORG_NAME,
        "type": info.org_type or "",
        "tagline": info.tagline or DEFAULT_TAGLINE,
        "logo": _safe_url(info.logo),
        "address": info.address or "",
        "phone": info.phone or "",
        "fax": info.fax or "",
        "email": info.email or "",
        "website": _safe_url(info.website),
        "map_url": _safe_url(info.map_url),
        "hours": _lines(info.reading_room_hours),
        "introduction": clean_html(info.introduction or ""),
        "leadership_info": clean_html(info.leadership_info or ""),
        "structure_info": clean_html(info.org_structure or ""),
        "reader_guide": clean_html(info.reader_guide or ""),
        "show_leaders": not cint(info.hide_leaders),
        "show_structure": not cint(info.hide_structure),
        "leaders": [{"full_name": row.full_name, "position": row.position or "", "photo": _safe_url(row.photo),
                     "bio": row.bio or ""} for row in leaders],
    }


def get_org_units() -> list[dict]:
    """Visible units as a nested list (children under `children`), ordered by display order then name.

    A hidden unit hides everything below it. One query, assembled in Python: the tree is small.
    """
    rows = frappe.get_all(
        "Organization Unit",
        filters={"is_visible": 1},
        fields=["name", "unit_name", "parent_organization_unit", "head_name", "head_position", "phone", "email",
                "description", "display_order"],
        order_by="display_order asc, unit_name asc",
        limit_page_length=0,
    )
    nodes = {row.name: {**row, "children": []} for row in rows}
    roots = []
    for row in rows:
        parent = row.parent_organization_unit
        if parent and parent in nodes:
            nodes[parent]["children"].append(nodes[row.name])
        elif not parent:
            roots.append(nodes[row.name])
        # a visible unit whose parent is hidden is dropped together with that parent
    return roots
