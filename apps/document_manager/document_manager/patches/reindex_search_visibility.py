import frappe


def execute():
    """The search index now carries `is_published` (and fail-closed priorities): rebuild it.

    A search-engine outage must never block `bench migrate`; the nightly reconcile job picks up
    anything that was missed.
    """
    try:
        from document_manager.document_manager.services.search_index import _get_index, reindex_all
        _get_index()  # applies the new filterable attributes
        reindex_all()
    except Exception:
        from document_manager.document_manager.services.errors import log_exception
        log_exception("Search Index Error", "Could not queue the search re-index during migrate")
