# -*- coding: utf-8 -*-
"""Query helpers that keep a list cheap on a table of a million rows."""

from contextlib import contextmanager

import frappe
from frappe import _

COUNT_CAP = 10_000
SCAN_SECONDS = 8
STATEMENT_TIMEOUT = 1969  # MariaDB: "Query execution was interrupted (max_statement_time exceeded)"


def capped_count(doctype: str, filters=None, or_filters=None, cap: int = COUNT_CAP) -> tuple[int, bool]:
    """(number of matching records, whether there are more than `cap`), through the permission-aware get_list.

    A substring search (`LIKE '%text%'`) cannot use an index: counting every match scans the whole table. A list never needs
    the exact figure past a few pages ("10.000+" says the same), so this stops at `cap` + 1 matches.
    """
    names = frappe.get_list(doctype, filters=filters, or_filters=or_filters, pluck="name", order_by="name asc",
                            page_length=cap + 1)
    return min(len(names), cap), len(names) > cap


def total_of_short_page(rows, page: int, page_size: int) -> int | None:
    """The exact total when the page just read is not full (nothing lies beyond it), else None.

    A search that matches little is the one that scans the whole table; counting it again would double the cost.
    """
    if len(rows) < page_size and (rows or page == 1):
        return (page - 1) * page_size + len(rows)
    return None


@contextmanager
def bounded_scan(seconds: int = SCAN_SECONDS):
    """Any statement inside the block that runs longer than `seconds` is aborted by MariaDB, and the caller gets a message that
    says what to do. A substring search over a million rows is slow by nature; without a ceiling a handful of them keep every
    database connection busy.
    """
    previous = frappe.db.sql("select @@max_statement_time")[0][0]
    frappe.db.sql("set session max_statement_time = %s", seconds)
    try:
        yield
    except Exception as error:
        if error.args and error.args[0] == STATEMENT_TIMEOUT:
            frappe.throw(_("Tìm kiếm mất quá nhiều thời gian. Hãy nhập từ khóa cụ thể hơn hoặc thu hẹp theo phông, hồ sơ, năm."))
        raise
    finally:
        frappe.db.sql("set session max_statement_time = %s", previous)
