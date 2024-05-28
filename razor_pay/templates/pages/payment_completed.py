from __future__ import unicode_literals
# import frappe
# from _future_ import unicode_literals
import frappe
import razorpay
from frappe import _

def get_context(context):
	context.orderid = frappe.form_dict.order
	order = frappe.get_doc("Order", order)
	context.key = order.validatekey
	pay = 0
	frappe.log_error(order.payment_status, "order.payment_status")
	if order.payment_status=="Paid":
		pay = 1
	frappe.log_error(pay, "pay")
	context.pay_status = pay