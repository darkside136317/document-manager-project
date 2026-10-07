from document_manager.document_manager.setup.install import set_upload_limit


def execute():
    """Existing sites accept the files the cataloguing screen accepts (see install.set_upload_limit)."""
    set_upload_limit()
