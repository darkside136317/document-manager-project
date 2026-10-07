# -*- coding: utf-8 -*-
"""Error logging helper.

`frappe.log_error(title, message)` takes the *title* first. Passing the human message as the
first positional argument (the old pattern in this app) stored it as the title and dropped the
traceback. Always go through `log_exception`.
"""

import frappe


def log_exception(title: str, detail: str | None = None) -> None:
    """Record the exception being handled (traceback included) in the Error Log. Never raises."""
    try:
        trace = frappe.get_traceback()
        message = f"{detail}\n\n{trace}" if detail else trace
        frappe.log_error(title=(title or "Error")[:140], message=message)
    except Exception:
        pass
