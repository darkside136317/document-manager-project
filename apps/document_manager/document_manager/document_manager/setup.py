"""Installation helpers for the Document Manager application."""

import json

import frappe


def after_migrate():
	"""Create or update the public Desk workspace after every migration."""
	_sync_dashboard_block()

	workspace_path = frappe.get_app_path(
		"document_manager", "workspace", "document_manager", "document_manager.json"
	)
	with open(workspace_path, encoding="utf-8") as workspace_file:
		workspace = json.load(workspace_file)

	if frappe.db.exists("Workspace", "Document Manager"):
		doc = frappe.get_doc("Workspace", "Document Manager")
		doc.update(workspace)
		doc.save(ignore_permissions=True)
	else:
		frappe.get_doc(workspace).insert(ignore_permissions=True)


def _sync_dashboard_block():
	"""Create the modular workspace overview block used by Document Manager."""
	block_name = "Document Manager Overview"
	template_path = frappe.get_app_path(
		"document_manager", "templates", "includes", "document_manager_dashboard.html"
	)
	with open(template_path, encoding="utf-8") as template_file:
		html = template_file.read()

	theme_path = frappe.get_app_path("document_manager", "public", "css", "theme-tokens.css")
	ui_path = frappe.get_app_path("document_manager", "public", "css", "document-manager-ui.css")
	
	with open(theme_path, encoding="utf-8") as f:
		theme_css = f.read()
	with open(ui_path, encoding="utf-8") as f:
		ui_css = f.read()

	values = {
		"html": html,
		"script": (
			'frappe.require("/assets/document_manager/js/document-manager-dashboard.js", '
			"() => window.DocumentManagerDashboard.init(root_element));"
		),
		"style": theme_css + "\n\n" + ui_css,
		"private": 0,
	}

	if frappe.db.exists("Custom HTML Block", block_name):
		block = frappe.get_doc("Custom HTML Block", block_name)
		block.update(values)
		block.save(ignore_permissions=True)
	else:
		frappe.get_doc({
			"doctype": "Custom HTML Block",
			"name": block_name,
			**values,
		}).insert(ignore_permissions=True)
