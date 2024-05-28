from __future__ import unicode_literals
# import frappe
# from _future_ import unicode_literals
import frappe
import razorpay
import requests
import json
from frappe import _
from frappe.utils import cstr, cint, flt, comma_or, getdate, nowdate, formatdate, format_time
from frappe.utils import cstr, encode
from cryptography.fernet import Fernet, InvalidToken 
from ecommerce_business_store.ecommerce_business_store.doctype.business_payment_gateway_settings.business_payment_gateway_settings import get_payments


def get_context(context):
	
	token = frappe.form_dict.token
	info =decrypt(token)
	order_id = info.split("||")[1]
	domain = info.split("||")[0]
	if order_id:
		url = domain + "/api/method/ecommerce_business_store.ecommerce_business_store.api.order_razor_pay_settings"
		headers = {"Accept": "application/json"} 
		parameters = {"OrderId": order_id}
		response = requests.get(url=url,params=parameters,headers=headers)
		data = response.json()
		catalog_settings =  data.get("message").get("CatalogSettings")
		gateway_settings =  data.get("message").get("Settings")
		order_info = data.get("message").get("Order")
		if order_info:
			if order_info.get("payment_status") == 'Pending' or order_info.get("payment_status")  == 'Partially Paid':
				if gateway_settings.get("api_key") != '' and gateway_settings.get("api_secret") != '':
					context.catalog_settings = catalog_settings
					context.gateway_settings = gateway_settings
					context.order_info = order_info
					context.domainurl = domain
		else:
			redirect_to_invalid()
	else:
		redirect_to_invalid()
	if not context.get('gateway_settings'):
		redirect_to_invalid()

@frappe.whitelist(allow_guest=True)
def redirect_to_invalid():
	frappe.redirect_to_message(_('Some information is missing'),
			_('Looks like someone sent you to an incomplete URL. Please ask them to look into it.'))
	frappe.local.flags.redirect_location = frappe.local.response.location
	raise frappe.Redirect


@frappe.whitelist(allow_guest=True)
def update_order_status(domain,order_id, transaction_id, capture=None):
	try:
		gateway_settings = None
		url = domain+ "/api/method/ecommerce_business_store.ecommerce_business_store.api.order_razor_pay_settings"
		headers = {"Accept": "application/json"} 
		parameters = {"OrderId": order_id}
		response = requests.get(url=url,params=parameters,headers=headers)
		data = response.json()
		catalog_settings =  data.get("message").get("CatalogSettings")
		gateway_settings =  data.get("message").get("Settings")
		order_info = data.get("message").get("Order")
		capture_payment = frappe.db.get_value('General Settings', None, 'capture_payment')
		transfer_id = complete_payment(gateway_settings, order_info, transaction_id)	
		url = domain+ "/api/method/ecommerce_business_store.ecommerce_business_store.api.update_razor_pay_order_status"
		headers = {"Accept": "application/json"} 
		parameters = {"OrderId": order_id,"TransactionId":transfer_id}
		response = requests.post(url=url,params=parameters,headers=headers)
		data = response.json()
		return "success"
	except Exception:
		frappe.log_error(frappe.get_traceback(), "ecommerce_business_store.ecommerce_business_store.api.update_order_status") 	

def complete_payment(gateway_settings, order_info, transaction_id):
	try:
		client = razorpay.Client(auth=(gateway_settings.get("api_key"), gateway_settings.get("api_secret")))
		client.payment.capture(transaction_id, int(order_info.get("total_amount")*100))
		transaction_id = transaction_id
		if gateway_settings.get("routing_enable") == 1:
			if gateway_settings.get("account_id") != '':
				order_total=order_info.get("total_amount") * (100 - gateway_settings.get("commission_percentage")) / 100
				amount = int(order_total * 100)
				BillingAddress = order_info.get("first_name")+" "+order_info.get("last_name")+","+order_info.get("address")+","+order_info.get("city")+","+order_info.get("state")+","+order_info.get("zipcode")+"-"+order_info.get("country")+","+order_info.get("phone")
				ShippingAddress = order_info.get("shipping_first_name")+"  "+order_info.get("shipping_last_name")+","+order_info.get("shipping_shipping_address")+","+order_info.get("shipping_city")+","+order_info.get("shipping_state")+","+order_info.get("shipping_zipcode")+"-"+order_info.get("shipping_country")+","+order_info.get("shipping_phone")
				Notes = {"Customer Name":order_info.get("customer_name"),"Customer Email":order_info.get("customer_email"),"OrderId":order_info.get("name"),"Billing Address":BillingAddress,"Shipping Address":ShippingAddress,"PaymentId":transaction_id}
				DATA = {'amount':amount,'currency':'INR','account':gateway_settings.get("account_id"),"notes":Notes}
				param = {
	            	'transfers': {
	                	'currency': {
	                    	'amount': amount,
	                    	'currency': 'INR',
	                    	'account': gateway_settings.get("account_id"),
	                    	'notes':Notes,
	                    	"linked_account_notes":["OrderId","Billing Address","Shipping Address","PaymentId"],
	                   
	                	}
	            	}
	       		}

				payment_transfer = client.payment.transfer(transaction_id, data=param)
				transfer = payment_transfer.get("items")[0]
				transfer_id = transfer.get("id")
				transaction_id = transfer_id
				
		return transaction_id
		
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "razor_pay.templates.pages.razor_pay_payment.complete_payment")
def encrypt(url):
	# if len(url) > 100:
		# encrypting > 100 chars will lead to truncation
		# frappe.throw(_('something went wrong during encryption'))

	cipher_suite = Fernet(encode(get_encryption_key()))
	cipher_text = cstr(cipher_suite.encrypt(encode(url)))
	return cipher_text

def decrypt(url):
	try:
		cipher_suite = Fernet(encode(get_encryption_key()))
		plain_text = cstr(cipher_suite.decrypt(encode(url)))
		return plain_text
	except InvalidToken:
		# encryption_key in site_config is changed and not valid
		frappe.throw(_('Encryption key is invalid, Please check site_config.json'))

def get_encryption_key():
	from frappe.installer import update_site_config

	if 'encryption_key' not in frappe.local.conf:
		encryption_key = Fernet.generate_key().decode()
		update_site_config('encryption_key', encryption_key)
		frappe.local.conf.encryption_key = encryption_key

	return frappe.local.conf.encryption_key
