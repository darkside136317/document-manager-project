# -*- coding: utf-8 -*-
"""Error logging helper.

`frappe.log_error(title, message)` takes the *title* first. Passing the human message as the
first positional argument (the old pattern in this app) stored it as the title and dropped the
traceback. Always go through `log_exception`.
"""

import random
import time

import frappe


def log_exception(title: str, detail: str | None = None) -> None:
    """Record the exception being handled (traceback included) in the Error Log. Never raises."""
    try:
        trace = frappe.get_traceback()
        message = f"{detail}\n\n{trace}" if detail else trace
        frappe.log_error(title=(title or "Error")[:140], message=message)
    except Exception:
        pass


def retry_on_deadlock(operation, attempts: int = 4):
    """Run `operation`, starting it again (after a rollback) when MariaDB aborts it because another
    transaction changed the same rows first: "Record has changed since last read" (1020) or a
    deadlock. Two background jobs and a user editing the same document do this to each other.
    """
    for attempt in range(attempts):
        try:
            return operation()
        except frappe.QueryDeadlockError:
            frappe.db.rollback()
            if attempt == attempts - 1:
                raise
            time.sleep(0.2 * (attempt + 1) + random.random() * 0.2)

