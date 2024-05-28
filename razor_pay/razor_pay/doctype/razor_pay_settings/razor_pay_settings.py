# -*- coding: utf-8 -*-
# Copyright (c) 2018, info@valiantsystems.com and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json, hmac, hashlib
from frappe.model.document import Document
from frappe.utils import cint, get_timestamp, getdate
from frappe.integrations.utils import make_post_request
from six import string_types
from datetime import datetime

class RazorPaySettings(Document):
	def on_update(self):
		payment_method=frappe.db.get_all('Payment Method',filters={"payment_method":"Razor Pay"},order_by='display_order',fields=['*'])
		if not payment_method:
			doc=frappe.new_doc("Payment Method")
			doc.payment_method="Razor Pay"
			doc.display_order=1
			doc.enable=1
			doc.payment_type="Online Payment"
			doc.redirect_controller=self.redirect_controller
			doc.additional_charge=0
			doc.save()

	def setup_subscription(self, **kwargs):
		start_date = get_timestamp(kwargs.get('subscription_details').get("start_date")) \
			if kwargs.get('subscription_details').get("start_date") else None

		subscription_details = {
			"plan_id": kwargs.get('subscription_details').get("plan_id"),
			"total_count": kwargs.get('subscription_details').get("billing_frequency"),
			"customer_notify": kwargs.get('subscription_details').get("customer_notify"),
			"notes": kwargs.get('subscription_details').get('notes') or None
		}

		if start_date:
			subscription_details['start_at'] = cint(start_date)

		if kwargs.get('addons'):
			convert_rupee_to_paisa(**kwargs)
			subscription_details.update({
				"addons": kwargs.get('addons')
			})

		try:
			resp = make_post_request(
				"https://api.razorpay.com/v1/subscriptions",
				auth=(self.api_key, self.api_secret),
				data=json.dumps(subscription_details),
				headers={
					"content-type": "application/json"
				}
			)
			
			if resp.get('status') == 'created':
				kwargs['subscription_id'] = resp.get('id')
				frappe.flags.status = 'created'
				return kwargs
			else:
				frappe.log_error(str(resp), 'Razorpay Failed while creating subscription')

		except:
			frappe.log_error(frappe.get_traceback())
			# failed
			pass

	def cancel_subscription(self, subscription_id):
		try:
			resp = make_post_request("https://api.razorpay.com/v1/subscriptions/{0}/cancel"
				.format(subscription_id), auth=(self.api_key,
					self.api_secret))
		except Exception:
			frappe.log_error(frappe.get_traceback())

	def update_subscription(self, subscription_id, **kwargs):
		try:
			data = {}
			if kwargs.get('remaining_count'):
				data['remaining_count'] = kwargs.get('remaining_count')
			if kwargs.get('plan_id'):
				data['plan_id'] = kwargs.get('plan_id')
			if kwargs.get('quantity'):
				data['quantity'] = kwargs.get('quantity')
			if kwargs.get('start_at'):
				data['start_at'] = kwargs.get('start_at')
			data['schedule_change_at'] = kwargs.get('schedule_change_at') or 'cycle_end'
			resp = make_post_request("https://api.razorpay.com/v1/subscriptions/{0}"
				.format(subscription_id), 
				auth=(self.api_key,	self.api_secret),
				data=json.dumps(data),
				headers={
					"content-type": "application/json"
				})
		except Exception:
			frappe.log_error(frappe.get_traceback())

	def create_customer(self, **kwargs):
		customer_details = {
			"name": kwargs.get('user_details').get("full_name"),
			"contact": kwargs.get('user_details').get("phone"),
			"email": kwargs.get('user_details').get("email"),
			"fail_existing": 0
		}

		try:
			resp = make_post_request(
				"https://api.razorpay.com/v1/customers",
				auth=(self.api_key, self.api_secret),
				data=json.dumps(customer_details),
				headers={
					"content-type": "application/json"
				}
			)

			if resp.get('id'):
				kwargs['customer_id'] = resp.get('id')
				return kwargs
			else:
				frappe.log_error(str(resp), 'Razorpay Failed while creating customer')

		except:
			frappe.log_error(frappe.get_traceback())
			# failed
			pass

	def generate_webhook_key(self):
		key = frappe.generate_hash(length=20)
		self.webhook_secret = key
		self.save()

		frappe.msgprint(
			frappe._("Here is your webhook secret, this will be shown to you only once.") + "<br><br>" + key,
			frappe._("Webhook Secret")
		)

	def verify_signature(self, body, signature, key):
		key = bytes(key, 'utf-8')
		body = bytes(body, 'utf-8')

		dig = hmac.new(key=key, msg=body, digestmod=hashlib.sha256)

		generated_signature = dig.hexdigest()
		result = hmac.compare_digest(generated_signature, signature)

		if not result:
			frappe.throw(frappe._('Razorpay Signature Verification Failed'), exc=frappe.PermissionError)

		return result

def convert_rupee_to_paisa(**kwargs):
	for addon in kwargs.get('addons'):
		addon['item']['amount'] *= 100

	frappe.conf.converted_rupee_to_paisa = True

def verify_signature(data):
	signature = frappe.request.headers.get('X-Razorpay-Signature')

	settings = frappe.get_doc("Razor Pay Settings")
	key = frappe.utils.password.get_decrypted_password("Razor Pay Settings", "Razor Pay Settings", fieldname='webhook_secret')

	settings.verify_signature(data, signature, key)

@frappe.whitelist(allow_guest=True)
def check_webhook(*args, **kwargs):
	try:
		data = frappe.request.get_data(as_text=True)
		verify_signature(data)

		if isinstance(data, string_types):
			data = json.loads(data)
		data = frappe._dict(data)
		data_json = json.dumps(data, indent=4, sort_keys=True)
		payment = data.payload.get("payment", {}).get("entity", {})
		# if data.event == 'payment.captured':
		# 	check_order = frappe.db.get_all('Order', filters={'transaction_id': payment.get('id')}, fields=['name', 'payment_status'])
		# 	print(check_order)
		if frappe.db.get_value('DocType', 'Subscription'):
			subscription = data.payload.get('subscription', {}).get('entity', {})
			if not subscription:
				return False
			__subscription = frappe.db.get_all('Subscription', filters={'subscription_id': subscription.get('id')}, fields=['name', 'party', 'party_type'])
			if not __subscription:
				return False
			party = frappe.get_doc(__subscription[0].party_type, __subscription[0].party)
			if data.event == "subscription.activated" and not party.customer_id:
				frappe.db.set_value('Customers', party.name, 'customer_id', subscription.get('customer_id'))
			if data.event == 'subscription.charged':
				plan_info = frappe.db.get_all('Subscription Plan', filters={'recurring_plan_id': subscription.get('plan_id')})
				if not plan_info:
					return False
				from subscription.subscription.api import update_subscription_order
				start_date = getdate(datetime.fromtimestamp(subscription.get('current_start')))
				payment_method = frappe.db.get_all('Payment Method', filters={'payment_method': 'Razor Pay'})
				update_subscription_order(party, 'Customers', plan_info[0].name, start_date, payment.get('id'), 'Razor Pay', payment_method[0].name)
			# if data.event == 'subscription.completed':
			# 	frappe.db.set_value('Customers', party.name, 'customer_id', '')
		return True
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), 'razorpay_webhook')
