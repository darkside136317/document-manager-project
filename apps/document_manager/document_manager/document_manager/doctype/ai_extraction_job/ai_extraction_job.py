"""Durable ERP-side record of an AI extraction request."""

from frappe.model.document import Document


class AIExtractionJob(Document):
    """Keep the immutable request and the latest verified AI result."""

