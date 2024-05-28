# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "razor_pay"
app_title = "Razor Pay"
app_publisher = "Valiant"
app_description = "Razor payment gateawy"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "kartheek@valiantsystems.com"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/razor_pay/css/razor_pay.css"
app_include_js = "/assets/razor_pay/js/rp_socket.js"

# include js, css files in header of web template
# web_include_css = "/assets/razor_pay/css/razor_pay.css"
# web_include_js = "/assets/razor_pay/js/razor_pay.js"
website_route_rules = [
 	{"from_route":"/payment-completed","to_route":"payment_completed"},
 	]
# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {"Order" : "public/js/order.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Website user home page (by function)
# get_website_user_home_page = "razor_pay.utils.get_home_page"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "razor_pay.install.before_install"
# after_install = "razor_pay.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "razor_pay.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
#	}
# }
doc_events = {
	"Order":{
		"on_cancel":"razor_pay.razor_pay.api.on_order_cancel"
	},
	"Return Request":{
		"on_update":"razor_pay.razor_pay.api.on_return_request_submit"
	},
	"Sales Invoice":{
		"on_cancel":"razor_pay.razor_pay.api.on_sales_invoice_cancel"
	},
}
# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"razor_pay.tasks.all"
# 	],
# 	"daily": [
# 		"razor_pay.tasks.daily"
# 	],
# 	"hourly": [
# 		"razor_pay.tasks.hourly"
# 	],
# 	"weekly": [
# 		"razor_pay.tasks.weekly"
# 	]
# 	"monthly": [
# 		"razor_pay.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "razor_pay.install.before_tests"

# Overriding Whitelisted Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "razor_pay.event.get_events"
# }

