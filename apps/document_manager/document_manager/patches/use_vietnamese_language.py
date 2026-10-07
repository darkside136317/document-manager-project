from document_manager.document_manager.setup.install import set_vietnamese_defaults


def execute():
    """Existing sites get the Vietnamese default language once (see install.set_vietnamese_defaults)."""
    set_vietnamese_defaults()
