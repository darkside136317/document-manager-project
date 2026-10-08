# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, now_datetime

DRAFT, COUNTING, DONE = "Nháp", "Đang kiểm kê", "Hoàn thành"
PAIRS = (("files", "recorded_files", "counted_files", "difference_files"),
         ("documents", "recorded_documents", "counted_documents", "difference_documents"),
         ("boxes", "recorded_boxes", "counted_boxes", "difference_boxes"))
RECORDED = ("recorded_files", "recorded_documents", "recorded_boxes")
LOCKED_COLUMNS = ("fonds", "recorded_files", "counted_files", "recorded_documents", "counted_documents",
                  "recorded_boxes", "counted_boxes", "counted", "note")


def snapshot(fonds: str) -> dict:
    """The figures the system holds for a fonds right now: files and documents counted, boxes as registered."""
    return {
        "recorded_files": frappe.db.count("Archival File", {"fonds": fonds}),
        "recorded_documents": frappe.db.count("Archive Document", {"fonds": fonds}),
        "recorded_boxes": cint(frappe.db.get_value("Fonds", fonds, "total_boxes")),
    }


class InventoryCheck(Document):
    """Tổng kiểm kê phông: số liệu sổ sách của từng phông đối chiếu với số đếm thực tế.

    The lines are taken from the system when the check is started (`populate`); the cataloguer then types the
    physical counts and ticks each fonds as counted. A completed check is read-only except for its remarks.
    """

    def validate(self):
        self.check_title = (self.check_title or "").strip()
        self._guard_completed()
        self._fill_recorded()
        seen = set()
        for row in self.get("items") or []:
            if row.fonds in seen:
                frappe.throw(_("Phông {0} xuất hiện hai lần trong danh sách kiểm kê").format(row.fonds))
            seen.add(row.fonds)
            for _kind, recorded, counted, difference in PAIRS:
                for field in (recorded, counted):
                    if cint(row.get(field)) < 0:
                        frappe.throw(_("Dòng {0}: số liệu không được âm").format(row.idx))
                row.set(difference, cint(row.get(counted)) - cint(row.get(recorded)) if cint(row.counted) else 0)
        self.total_difference = sum(
            1 for row in self.get("items") or []
            if cint(row.counted) and any(cint(row.get(d)) for _k, _r, _c, d in PAIRS))
        if self.status == DONE and not self.completed_on:
            self._require_all_counted()
            self.completed_on = now_datetime()
        if self.status != DONE:
            self.completed_on = None

    def _fill_recorded(self):
        """The "sổ sách" figures are the system's, never typed: kept from the saved lines, or read for a new fonds."""
        if self.flags.snapshot_fresh:
            return
        before = self.get_doc_before_save()
        saved = {row.fonds: row for row in before.items} if before else {}
        for row in self.get("items") or []:
            source = saved.get(row.fonds)
            row.update({key: source.get(key) for key in RECORDED} if source else snapshot(row.fonds))

    def _guard_completed(self):
        before = self.get_doc_before_save()
        if not before or before.status != DONE or self.status != DONE:
            return
        changed = len(before.items) != len(self.items) or any(
            a.get(f) != b.get(f) for a, b in zip(before.items, self.items) for f in LOCKED_COLUMNS)
        if changed or before.fonds != self.fonds or before.check_date != self.check_date:
            frappe.throw(_("Đợt kiểm kê đã hoàn thành, không sửa được số liệu. Hãy mở lại đợt kiểm kê trước."))

    def _require_all_counted(self):
        missing = [row.fonds for row in self.get("items") or [] if not cint(row.counted)]
        if not self.get("items"):
            frappe.throw(_("Chưa có phông nào trong đợt kiểm kê"))
        if missing:
            frappe.throw(_("Còn {0} phông chưa được đánh dấu đã kiểm: {1}").format(len(missing), ", ".join(missing[:5])))

    # -- actions (called by api/inventory.py) ------------------------------------------------------------------------

    def populate(self):
        """(Re)build the lines from the system's figures; counts typed so far are kept for fonds already listed."""
        if self.status == DONE:
            frappe.throw(_("Đợt kiểm kê đã hoàn thành"))
        scope = [self.fonds] if self.fonds else frappe.get_all("Fonds", pluck="name", order_by="fonds_name asc")
        if not scope:
            frappe.throw(_("Chưa có phông lưu trữ để kiểm kê"))
        kept = {row.fonds: row for row in self.get("items") or []}
        self.set("items", [])
        for fonds in scope:
            figures = snapshot(fonds)
            old = kept.get(fonds)
            self.append("items", {
                "fonds": fonds, **figures,
                "counted_files": old.counted_files if old else figures["recorded_files"],
                "counted_documents": old.counted_documents if old else figures["recorded_documents"],
                "counted_boxes": old.counted_boxes if old else figures["recorded_boxes"],
                "counted": old.counted if old else 0, "note": old.note if old else "",
            })
        self.status = COUNTING
        self.checked_by = self.checked_by or frappe.session.user
        self.flags.snapshot_fresh = True
        self.save()

    def complete(self):
        if self.status == DONE:
            frappe.throw(_("Đợt kiểm kê đã hoàn thành"))
        self._require_all_counted()
        self.status = DONE
        self.save()

    def reopen(self):
        if self.status != DONE:
            frappe.throw(_("Đợt kiểm kê chưa hoàn thành"))
        self.status = COUNTING
        self.completed_on = None
        self.save()
