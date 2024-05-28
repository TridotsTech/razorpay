from __future__ import unicode_literals
# import frappe
# from _future_ import unicode_literals
import frappe
import razorpay
from frappe import _
from ecommerce_business_store.ecommerce_business_store.doctype.business_payment_gateway_settings.business_payment_gateway_settings import get_payments
from ecommerce_business_store.utils.setup import get_settings_value_from_domain, get_settings_from_domain
from ecommerce_business_store.ecommerce_business_store.api import check_domain,calculate_shipment_charges

def get_context(context):
	shipmentid = frappe.form_dict.shipmentid
	shipment = frappe.get_doc("Shipment Bag",shipmentid)
	shipmentbag = frappe.db.get_all('Shipment Bag Item',filters={'parent':shipmentid},fields=['*'])

	if len(shipmentbag)>0:
		gateway_settings = None
		total_amount = 0
		customers = frappe.db.get_all('Customers',filters={'user_id':frappe.session.user},fields=['*'])
		customer = customers[0]
		context.customer = customer

		for x in shipment.items:
			total_amount += x.shipping_charge
		total_amount = calculate_shipment_charges(shipmentid)
		context.payable_amount = total_amount
		if shipment.business:
			gateway_settings = get_payments(shipment.business, 'Razorpay')
		if not gateway_settings:
			gateway_settings = frappe.get_single('Razor Pay Settings')
		if gateway_settings.api_key != '' and gateway_settings.api_secret != '':
			if not context.catalog_settings:
				context.catalog_settings = get_settings_from_domain('Catalog Settings')
			context.gateway_settings = gateway_settings
	context.order_id = shipmentid
	if not context.gateway_settings:
		frappe.redirect_to_message(_('Some information is missing'),
			_('Looks like someone sent you to an incomplete URL. Please ask them to look into it.'))
		frappe.local.flags.redirect_location = frappe.local.response.location
		raise frappe.Redirect	

@frappe.whitelist(allow_guest=True)
def update_order_status(order_id, transaction_id, capture=None):
	try:
		validation_message = ""
		shipmentid = order_id
		shipment = frappe.get_doc("Shipment Bag",shipmentid)
		shipmentbag = frappe.db.get_all('Shipment Bag Item',filters={'parent':shipmentid},fields=['*'])
		if len(shipmentbag)>0:
			order_id = shipmentbag[0].order_id
			gateway_settings = None
			order_info=frappe.get_doc("Order",order_id)
			if order_info.get('business'):
				gateway_settings = get_payments(order_info.business, 'Razorpay')
			if not gateway_settings:
				if order_info.order_item[0].business:
					gateway_settings = get_payments(order_info.order_item[0].business, 'Razorpay')
			if not gateway_settings:
				gateway_settings=frappe.get_single('Razor Pay Settings')
			capture_payment = 1
			if check_domain('restaurant'):
				capture_payment = get_settings_value_from_domain('Business Setting', 'capture_payment', business=order_info.get('business'))
			else:
				capture_payment = 1
			if int(capture_payment) == 1:
				complete_payment(gateway_settings, order_info, transaction_id, shipmentid)			
			else:
				if int(capture) == 1:
					complete_payment(gateway_settings, order_info, transaction_id, shipmentid)
				else:
					order_info.transaction_id = transaction_id
					order_info.save(ignore_permissions=True)
			
		return {"status":True,"message":validation_message}
	except Exception:
		frappe.log_error(frappe.get_traceback(), "ecommerce_business_store.ecommerce_business_store.api.update_order_status") 	


def complete_payment(gateway_settings, order_info, transaction_id, shipmentid):
	try:
		shipment = frappe.get_doc("Shipment Bag",shipmentid)
		if (not check_domain('multi_vendor') and not check_domain('restaurant')) or check_domain('saas'):
			client = razorpay.Client(auth=(gateway_settings.api_key, gateway_settings.api_secret))
			order_settings = get_settings_from_domain('Order Settings')
			total_amount = 0
			for x in shipment.items:
				total_amount += x.shipping_charge
			total_amount = calculate_shipment_charges(shipmentid)
			payable_amount = total_amount
			amount_to_capture = int(payable_amount*100)
			payment = client.payment.fetch(transaction_id)
			print(transaction_id)
			transfer_id = transaction_id
			if payment.get('captured') != True:
				client.payment.capture(transaction_id, amount_to_capture)
			if gateway_settings.get('routing_enable') == 1:
				if gateway_settings.account_id != '':
					order_id = order_info.name
					advance_amount = payable_amount
					order_total=advance_amount * (100 - gateway_settings.commission_percentage) / 100
					# order_total=order_info.outstanding_amount * (100 - gateway_settings.commission_percentage) / 100
					amount = int(order_total * 100)
					Notes = {"Customer Name":order_info.customer_name,"Customer Email":order_info.customer_email,"Shipment":shipmentid,"PaymentId":transaction_id}
					DATA = {'amount':amount,'currency':'INR','account':gateway_settings.account_id,"notes":Notes}
					param = {
		            	'transfers': {
		                	'currency': {
		                    	'amount': amount,
		                    	'currency': 'INR',
		                    	'account': gateway_settings.account_id,
		                    	'notes':Notes,
		                    	"linked_account_notes":["Customer Name","Customer Email","Shipment","PaymentId"],
		                   
		                	}
		            	}
		       		}
					payment_transfer = client.payment.transfer(transaction_id, data=param)
					transfer = payment_transfer.get("items")[0]
					transfer_id = transfer.get("id")
					shipmentbag = frappe.db.get_all('Shipment Bag Item',filters={'parent':shipmentid},fields=['*'])
					for item in shipmentbag:
						order_info = frappe.get_doc("Order", item.order_id)
						from ecommerce_business_store.accounts.api import make_payment as _make_payment
						_make_payment(order=order_info.name, mode_of_payment='Razor Pay', amount=item.shipping_charge)
			shipment = frappe.get_doc("Shipment Bag",shipmentid)
			shipment.is_paid = 1
			shipment.transaction_id = transfer_id
			shipment.save(ignore_permissions=True)
			return "success"
		
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "razor_pay.templates.pages.razorpay_checkout.complete_payment")


@frappe.whitelist(allow_guest=True)
def check_domain(domain_name):
	try:
		from frappe.core.doctype.domain_settings.domain_settings import get_active_domains
		domains_list=get_active_domains()
		domains=frappe.cache().hget('domains','domain_constants')
		if not domains:
			domains = get_domains_data()
		if domains[domain_name] in domains_list:
			return True
		return False
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "ecommerce_business_store.ecommerce_business_store.api.check_domain")
