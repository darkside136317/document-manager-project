# -*- coding: utf-8 -*-
from frappe.model.document import Document


class DocumentManagerSettings(Document):
    """Business parameters of the system (backup, integrity check, activity log).

    Connection settings for MongoDB Atlas and Meilisearch are infrastructure, not business data:
    they live in `site_config.json` / the environment (see docker/.env). The live status of those
    services is reported by `api.admin.get_service_health`.
    """
