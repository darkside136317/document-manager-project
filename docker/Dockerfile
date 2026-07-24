# =============================================================================
# Custom Dockerfile — Build Frappe/ERPNext image WITH document_manager app
# =============================================================================
# Build context: project root (document-manager-project/)
#
# Build command (from project root):
#   docker build --no-cache -t docmanager-custom:v16.26.2 --build-arg ERPNEXT_VERSION=v16.26.2 -f docker/Dockerfile .
# =============================================================================

ARG ERPNEXT_VERSION=v16.26.2
FROM frappe/erpnext:${ERPNEXT_VERSION}

# Switch to root for system-level installs
USER root

# Install system dependencies for text extraction
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Switch back to frappe user
USER frappe

# Copy custom app source code into the bench apps directory
COPY --chown=frappe:frappe apps/document_manager /home/frappe/frappe-bench/apps/document_manager

# Install app into the Frappe VIRTUALENV (not system pip!)
# Frappe uses /home/frappe/frappe-bench/env/ as its virtualenv
RUN /home/frappe/frappe-bench/env/bin/pip install --no-cache-dir -e /home/frappe/frappe-bench/apps/document_manager

# Expose the app's public design-system assets to Nginx in every container.
# The link is baked into the image so backend and frontend serve identical UI files.
RUN ln -sfn \
    /home/frappe/frappe-bench/apps/document_manager/document_manager/public \
    /home/frappe/frappe-bench/assets/document_manager
