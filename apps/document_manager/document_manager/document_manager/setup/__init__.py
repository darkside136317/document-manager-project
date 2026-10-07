"""Install / migrate hooks of the Document Manager application."""

from document_manager.document_manager.setup.install import after_install, after_migrate, seed_all

__all__ = ["after_install", "after_migrate", "seed_all"]
