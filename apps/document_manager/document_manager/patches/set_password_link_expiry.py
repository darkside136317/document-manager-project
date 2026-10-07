from document_manager.document_manager.setup.install import set_password_link_expiry


def execute():
    """Existing sites: one-time password links expire (see install.set_password_link_expiry)."""
    set_password_link_expiry()
