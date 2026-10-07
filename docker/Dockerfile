# =============================================================================
# Custom Dockerfile — Build Frappe/ERPNext image WITH document_manager app
# =============================================================================
# Build context: project root (document-manager-project/)
#
# Build command (from project root):
#   docker build --no-cache -t docmanager-custom:v16.26.2 --build-arg ERPNEXT_VERSION=v16.26.2 -f docker/Dockerfile .
# =============================================================================

ARG ERPNEXT_VERSION=v16.26.2

# -----------------------------------------------------------------------------
# Stage 1 - build the staff single-page application (Vue 3 + Vite).
# vite.config.js writes the bundle to ../document_manager/public/staff.
# -----------------------------------------------------------------------------
FROM node:20-slim AS staff-ui
WORKDIR /src/apps/document_manager/frontend
COPY apps/document_manager/frontend/package.json apps/document_manager/frontend/package-lock.json ./
RUN npm ci
COPY apps/document_manager/frontend/ ./
RUN npm test && npm run build

# -----------------------------------------------------------------------------
# Stage 2 - Frappe / ERPNext image with the app
# -----------------------------------------------------------------------------
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

# The built staff UI (the host's public/staff is excluded by .dockerignore: always build it here)
COPY --from=staff-ui --chown=frappe:frappe /src/apps/document_manager/document_manager/public/staff      /home/frappe/frappe-bench/apps/document_manager/document_manager/public/staff

# Install app into the Frappe VIRTUALENV (not system pip!)
# Frappe uses /home/frappe/frappe-bench/env/ as its virtualenv
RUN /home/frappe/frappe-bench/env/bin/pip install --no-cache-dir -e /home/frappe/frappe-bench/apps/document_manager

# Expose the app's public design-system assets to Nginx in every container.
# The link is baked into the image so backend and frontend serve identical UI files.
RUN ln -sfn \
    /home/frappe/frappe-bench/apps/document_manager/document_manager/public \
    /home/frappe/frappe-bench/assets/document_manager
