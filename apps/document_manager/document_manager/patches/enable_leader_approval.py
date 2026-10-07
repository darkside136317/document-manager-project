from document_manager.document_manager.setup.install import ensure_reader_settings_defaults, flag_levels_needing_leader


def execute():
    """Existing sites: the Archive Leader role arrives with defaults for the new limits, and the
    confidentiality levels above "Thường" send slips to a leader (see install.py)."""
    from document_manager.document_manager.setup.install import ensure_roles
    ensure_roles()
    ensure_reader_settings_defaults()
    flag_levels_needing_leader()
