from __future__ import unicode_literals
# import frappe
# from _future_ import unicode_literals
import frappe
import razorpay
from frappe import _
from ecommerce_business_store_singlevendor.utils.setup import get_settings_from_domain

def get_context(context):
	order_id = frappe.form_dict.order_id
	# key = frappe.form_dict.key
	if order_id:
		order_info = frappe.get_doc("Order",order_id)
		context.order_from = order_info.order_from
		if order_info:
			# if key==order_info.validatekey:pass
			if order_info.order_from=="WhatsApp":
				from frappe.utils import time_diff, time_diff_in_seconds
				from datetime import datetime
				if order_info.key_expiry_time:
					time = time_diff_in_seconds(datetime.now(), order_info.key_expiry_time)
					if time > (30*60):
						frappe.throw(_('Page has expired!'),frappe.PermissionError)
			if order_info.order_from=="WhatsApp" and order_info.customer and (not frappe.session.user or frappe.session.user=="Guest"):
				usr, pwd = frappe.db.get_value("Customers", {"name":order_info.customer}, ["user_id", "new_password"])
				frappe.local.login_manager.authenticate(usr, pwd)
				frappe.local.login_manager.post_login()
				frappe.local.flags.redirect_location = '/razor_pay_checkout?order_id='+order_id+'&&key='+key
				raise frappe.Redirect
			if order_info.order_from=="WhatsApp" and order_info.customer and frappe.session.user!="Guest":
				context.catalog_settings = get_settings_from_domain('Catalog Settings', None)
				active_theme = None
				if not active_theme:
					theme = frappe.db.get_all('Web Theme', filters={'is_active': 1})
					if theme:
						active_theme = theme[0].name
				if active_theme:
					theme_settings = frappe.get_doc('Web Theme', active_theme)
					for k in ["enable_view_tracking"]:
						if hasattr(theme_settings, k):
							context[k] = theme_settings.get(k)
					context.theme_settings = theme_settings
				context.gateway_settings = frappe.get_single('Razor Pay Settings')
			if order_info.payment_status == 'Pending' or order_info.payment_status  == 'Partially Paid':
				customers = frappe.db.get_all('Customers',filters={'user_id':frappe.session.user},fields=['*'])
				customer = customers[0]
				if order_info.is_shipment_bag_item==1 and order_info.shipment_charge:
					order_info.outstanding_amount = order_info.outstanding_amount
				context.order_info = order_info
				context.order_id = order_info.name
				

				# check razor pay subscription
				subscription_id = ''
				if order_info.naming_series == 'SUB-ORD-' and frappe.db.get_value('DocType', 'Subscription Plan'):
					from subscription.subscription.doctype.subscription_settings.subscription_settings import create_payment_subscription
					if not customer.get('subscription_id'):
						plan_id = next((x.item for x in order_info.order_item if x.order_item_type == 'Subscription Plan'), None)
						if plan_id:
							subscription = create_payment_subscription('Customers', customer.name, plan_id)
							if subscription.get('subscription_id'):
								subscription_id = subscription.get('subscription_id')
					else:
						subscription_id = customer.get('subscription_id')
				context.subscription_id = subscription_id
				# Inserted by suguna on 17/08/20
				context.payable_amount = 0
				if not context.order_settings:
					context.order_settings = get_settings_from_domain('Order Settings')
				if context.order_settings.enable_preorder==1 and order_info.advance_amount > 0 and order_info.payment_status!="Partially Paid":
					context.payable_amount = order_info.advance_amount
					
				else:
					
					context.payable_amount = order_info.outstanding_amount
				# end
				

				if check_domain('saas'):
					check_order = frappe.db.get_all('Vendor Orders', filters={'order_reference': order_info.name})
					if check_order:
						context.order_id = check_order[0].name
				context.customer = customer
				gateway_settings = None
				# if order_info.get('business'):
				# 	gateway_settings = get_payments(order_info.business, 'Razorpay')
				# if not gateway_settings:
				# 	if order_info.order_item[0].business:
				# 		gateway_settings = get_payments(order_info.order_item[0].business, 'Razorpay')
				if not gateway_settings:
					gateway_settings = frappe.get_single('Razor Pay Settings')
				if gateway_settings.api_key != '' and gateway_settings.api_secret != '':
					if not context.catalog_settings:
						context.catalog_settings = get_settings_from_domain('Catalog Settings')
					context.gateway_settings = gateway_settings
			else:
				order = frappe.get_doc('Order', order_id)
				order.docstatus = 1
				order.save(ignore_permissions=True)
				if order_info.order_from=="WhatsApp":
					frappe.local.flags.redirect_location = '/payment-completed?order='+order_id
					raise frappe.Redirect
				else:
					frappe.local.flags.redirect_location = '/thankyou'
					raise frappe.Redirect
		context.order_info = order_info
	if not context.gateway_settings:
		frappe.redirect_to_message(_('Some information is missing'),
			_('Looks like someone sent you to an incomplete URL. Please ask them to look into it.'))
		frappe.local.flags.redirect_location = frappe.local.response.location
		raise frappe.Redirect	

@frappe.whitelist(allow_guest=True)
def update_order_status(order_id, transaction_id, capture=None):
	try:
		validate_stock = True
		validation_message = ""
		# if not check_domain('restaurant'):
		# 	validate_stock,validation_message = validate_products_stock(order_id)
		if validate_stock:
			gateway_settings = None
			order_info=frappe.get_doc("Order",order_id)
			# if order_info.get('business'):
			# 	gateway_settings = get_payments(order_info.business, 'Razorpay')
			# if not gateway_settings:
			# 	if order_info.order_item[0].business:
			# 		gateway_settings = get_payments(order_info.order_item[0].business, 'Razorpay')
			if not gateway_settings:
				gateway_settings=frappe.get_single('Razor Pay Settings')
			capture_payment = 1
			# if check_domain('restaurant'):
			# 	capture_payment = get_settings_value_from_domain('Business Setting', 'capture_payment', business=order_info.get('business'))
			# else:
			# 	capture_payment = 1
			if int(capture_payment) == 1:
				complete_payment(gateway_settings, order_info, transaction_id)			
			else:
				if capture and int(capture) == 1:
					complete_payment(gateway_settings, order_info, transaction_id)
				else:
					order_info.transaction_id = transaction_id
					order_info.save(ignore_permissions=True)
			
		return {"status":validate_stock,"message":validation_message}
	except Exception:
		frappe.log_error(frappe.get_traceback(), "ecommerce_business_store.ecommerce_business_store.api.update_order_status") 	

def validate_products_stock(order_id):
	order_items = frappe.db.get_all("Order Item",filters={"parent":order_id},fields=['*'])
	validation_message = ""
	validate_stock = True
	for order_item in order_items:
		if order_item.order_item_type == "Product":
			product = frappe.get_doc("Product",order_item.item)
			if not order_item.is_free_item == 1:
				if product.inventory_method == "Track Inventory":
					if not int(product.stock) >= int(order_item.quantity) :
						validate_stock = False
						if int(product.stock) == 0:
							validation_message += _('Sorry! no stock available for <b class="message-product-title">{0}</b>').format(product.item)+"<br/>"
						else:
							validation_message += _('Sorry! stock available for <b class="message-product-title">{0}</b> is {1}').format(product.item,product.stock)+"<br/>"
				if product.inventory_method == "Track Inventory By Product Attributes":
					from ecommerce_business_store.ecommerce_business_store.api import validate_attributes_stock
					response = validate_attributes_stock(product.name,order_item.attribute_ids,order_item.attribute_description,order_item.quantity)
					if response.get("status") == "Failed" :
						validate_stock = False
						if int(response.get("stock")) == 0:
							validation_message += _('Sorry! no stock available for <b class="message-product-title">{0}</b>').format(product.item)+"<br/>"
						else:
							validation_message += _('Sorry! stock available for <b class="message-product-title">{0}</b> is {1}').format(product.item,int(response.get("stock")))+"<br/>"
	return validate_stock,validation_message

def complete_payment(gateway_settings, order_info, transaction_id):
	try:
		# if (not check_domain('multi_vendor') and not check_domain('restaurant')) or check_domain('saas'):
			client = razorpay.Client(auth=(gateway_settings.api_key, gateway_settings.api_secret))
			order_settings = get_settings_from_domain('Order Settings')
			# if check_domain('saas') and not check_domain('restaurant'):
			# 	check_order = frappe.db.get_all('Vendor Orders', filters={'order_reference': order_info.name},fields=['*'])
			# 	payment = client.payment.fetch(transaction_id)
			# 	if payment.get('captured') != True:
			# 		client.payment.capture(transaction_id, int(order_info.outstanding_amount*100))
			# else:
			# Inserted by suguna on 17/08/20
			payable_amount = 0
			# if order_settings.enable_preorder==1:
			if order_info.advance_amount > 0 and order_info.payment_status!="Partially Paid":
				payable_amount = order_info.advance_amount
			else:
				payable_amount = order_info.outstanding_amount
			# else:
			# 	payable_amount = order_info.outstanding_amount
			# end
			# #by siva 11/02/2021
			if order_info.is_shipment_bag_item==1:
				payable_amount = payable_amount
			# #end
			amount_to_capture = int(payable_amount*100)
			payment = client.payment.fetch(transaction_id)
			# frappe.log_error(title="payment obj",message=payment)
			if payment.get('captured') != True:
				# by gopi on 5/2/24
				# client.payment.capture(transaction_id, amount_to_capture)
				payable_amount = int(payment.get("amount"))
				client.payment.capture(transaction_id, payable_amount)
				# end
			if gateway_settings.get('routing_enable') == 1:
				if gateway_settings.account_id != '':
					order_id = order_info.name
					# if check_domain('saas'):
					# 	check_order = frappe.db.get_all('Vendor Orders', filters={'order_reference': order_id})
					# 	if check_order:
					# 		order_id = check_order[0].name
					# Inserted by suguna on 17/08/20
					if order_settings.enable_preorder==1:
						if order_info.advance_amount > 0 and order_info.payment_status!="Partially Paid":
							advance_amount = order_info.advance_amount
						else:
							advance_amount = order_info.outstanding_amount
					else:
						advance_amount = order_info.outstanding_amount
					# end
					#by siva 11/02/2021
					if order_info.is_shipment_bag_item==1:
						advance_amount = advance_amount
					#end
					order_total=advance_amount * (100 - gateway_settings.commission_percentage) / 100
					# order_total=order_info.outstanding_amount * (100 - gateway_settings.commission_percentage) / 100
					amount = int(order_total * 100)
					BillingAddress = order_info.first_name+" "+order_info.last_name+","+order_info.address+","+order_info.city
					if order_info.state:
						BillingAddress += ","+order_info.state
					if order_info.zipcode:
						BillingAddress += ","+order_info.zipcode
					if order_info.country:
						BillingAddress +=  "-"+order_info.country
					if order_info.phone:
						BillingAddress += "," +order_info.phone
					ShippingAddress = ""
					if order_info.shipping_first_name:
						ShippingAddress += order_info.shipping_first_name
					if order_info.shipping_last_name:
						ShippingAddress += " "+order_info.shipping_last_name
					if order_info.shipping_shipping_address:
						ShippingAddress += ","+order_info.shipping_shipping_address
					if order_info.shipping_city:
						ShippingAddress += ","+order_info.shipping_city
					if order_info.shipping_state:
						ShippingAddress += ","+order_info.shipping_state
					if order_info.shipping_zipcode:
						ShippingAddress += ","+order_info.shipping_zipcode
					if order_info.shipping_country:
						ShippingAddress += "-"+order_info.shipping_country
					if order_info.shipping_phone:
						ShippingAddress += ","+order_info.shipping_phone
					
					Notes = {"Customer Name":order_info.customer_name,"Customer Email":order_info.customer_email,"OrderId":order_id,"Billing Address":BillingAddress,"Shipping Address":ShippingAddress,"PaymentId":transaction_id}
					DATA = {'amount':amount,'currency':'INR','account':gateway_settings.account_id,"notes":Notes}
					param = {
		            	'transfers': {
		                	'currency': {
		                    	'amount': amount,
		                    	'currency': 'INR',
		                    	'account': gateway_settings.account_id,
		                    	'notes':Notes,
		                    	"linked_account_notes":["Customer Name","Customer Email","OrderId","Billing Address","Shipping Address","PaymentId"],
		                   
		                	}
		            	}
		       		}
					payment_transfer = client.payment.transfer(transaction_id, data=param)
					transfer = payment_transfer.get("items")[0]
					transfer_id = transfer.get("id")
					from ecommerce_business_store_singlevendor.accounts.api import make_payment as _make_payment
					# Inserted by suguna on 17/08/20
					if order_settings.enable_preorder==1 and order_info.advance_amount > 0 and order_info.payment_status!="Partially Paid":
						payment_amout = order_info.advance_amount
					else:
						payment_amout = order_info.outstanding_amount
					# end
					#by siva 11/02/2021
					if order_info.is_shipment_bag_item==1:
						payment_amout = payment_amout
					#end
					_make_payment(order=order_info.name, mode_of_payment='Razor Pay', amount=payment_amout,transaction_id=transaction_id)
					# submit_order =get_settings_value_from_domain('Order Settings','submit_order')
					submit_order = get_settings_from_domain('Order Settings').get('submit_order')
					if submit_order:
						order_info = frappe.get_doc(order_info.doctype, order_info.name) 
						# Inserted by suguna on 17/08/20
						if order_settings.enable_preorder==1 and order_info.advance_amount > 0 and order_info.payment_status!="Partially Paid":
							total_amount = order_info.advance_amount
						else:
							total_amount = order_info.total_amount
						# End
						#by siva 11/02/2021
						if order_info.is_shipment_bag_item==1:
							total_amount = total_amount
						#end
						order_info.docstatus = 1
						# order_info.payment_status='Paid'
						# order_info.outstanding_amount = 0	
						order_info.paid_amount = total_amount
						order_info.transaction_id = transfer_id
						order_info.save(ignore_permissions=True)
			else:
				from ecommerce_business_store_singlevendor.accounts.api import make_payment as _make_payment
				# Inserted by suguna on 17/08/20
				if  order_info.advance_amount > 0 and order_info.payment_status!="Partially Paid":
					payment_amount = order_info.advance_amount
				else:
					payment_amount = order_info.outstanding_amount
				# End
				#by siva 11/02/2021
				if order_info.is_shipment_bag_item==1:
					payment_amount = payment_amount
				#end
				#by gopi on 5/2/24
				payment_amount = payment.get("amount") / 100
				# end
				_make_payment(order=order_info.name, mode_of_payment='Razor Pay', amount=payment_amount,payment_type='Receive',transaction_id=transaction_id)
				# _make_payment(order=order_info.name, mode_of_payment='Razor Pay', amount=payment_amount)
				# submit_order=get_settings_value_from_domain('Order Settings','submit_order')
				submit_order = get_settings_from_domain('Order Settings').get('submit_order')
				if submit_order:
					order_info = frappe.get_doc(order_info.doctype, order_info.name) 
					if order_settings.enable_preorder==1 and order_info.advance_amount > 0 and order_info.payment_status!="Partially Paid":
						total_amount = order_info.advance_amount
					else:
						total_amount = order_info.total_amount
					#by siva 11/02/2021
					if order_info.is_shipment_bag_item==1:
						total_amount = total_amount
					#end
					order_info.docstatus = 1
					# order_info.payment_status='Paid'
					# order_info.outstanding_amount = 0	
					order_info.paid_amount = total_amount
					order_info.transaction_id = transaction_id
					order_info.save(ignore_permissions=True)
					#from ecommerce_business_store.ecommerce_business_store.doctype.order.order import update_giftcard_payments as update_giftcard_payments
					#update_giftcard_payments(order_info.name,order_info.transaction_id)
			return "success"
		# else:
		# 	multi_vendor_payments(gateway_settings, order_info, transaction_id)
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "razor_pay.templates.pages.razor_pay_checkout.complete_payment")

@frappe.whitelist(allow_guest=True)
def multi_vendor_payments(gateway_settings, order_info, transaction_id):
	client = razorpay.Client(auth=(gateway_settings.api_key, gateway_settings.api_secret))
	payment = client.payment.fetch(transaction_id)
	if payment.get('captured') != True:
		client.payment.capture(transaction_id, int(order_info.outstanding_amount*100))
	from ecommerce_business_store_singlevendor.accounts.api import make_payment as _make_payment
	_make_payment(order=order_info.name, mode_of_payment='Razor Pay',  amount=order_info.outstanding_amount)
	# submit_order=get_settings_value_from_domain('Order Settings','submit_order')
	submit_order = get_settings_from_domain('Order Settings').get('submit_order')
	if submit_order:
		order_info = frappe.get_doc(order_info.doctype, order_info.name) 
		order_info.docstatus = 1
		# order_info.payment_status='Paid'
		# order_info.outstanding_amount = 0	
		order_info.paid_amount = order_info.total_amount
		order_info.transaction_id = transaction_id
		order_info.save(ignore_permissions=True)
	if not check_domain('restaurant'):
		vendor_orders = frappe.db.get_all('Vendor Orders',fields=['*'],filters={"order_reference":order_info.name})
		for vendor_order in vendor_orders:
			routing_info = frappe.db.get_all('Razorpay Vendor Routing',fields=['*'],filters={"vendor":vendor_order.business})
			if routing_info:
				order_total=vendor_order.total_amount_for_vendor * (100 - routing_info[0].commission_percentage) / 100
				amount = int(order_total * 100)
				BillingAddress = order_info.first_name+" "+order_info.last_name+","+order_info.address+","+order_info.city+","+order_info.state+","+order_info.zipcode+"-"+order_info.country+","+order_info.phone
				ShippingAddress = order_info.shipping_first_name+"  "+order_info.shipping_last_name+","+order_info.shipping_shipping_address+","+order_info.shipping_city+","+order_info.shipping_state+","+order_info.shipping_zipcode+"-"+order_info.shipping_country+","+order_info.shipping_phone
				Notes = {"Customer Name":vendor_order.customer_name,"Customer Email":vendor_order.customer_email,"OrderId":vendor_order.name,"Billing Address":BillingAddress,"Shipping Address":ShippingAddress,"PaymentId":transaction_id}
				DATA = {'amount':amount,'currency':'INR','account':routing_info[0].account_id,"notes":Notes}
				param = {
		            	'transfers': {
		                	'currency': {
		                    	'amount': amount,
		                    	'currency': 'INR',
		                    	'account': routing_info[0].account_id,
		                    	'notes':Notes,
		                    	"linked_account_notes":["Customer Name","Customer Email","OrderId","Billing Address","Shipping Address","PaymentId"],
		                   
		                	}
		            	}
		       		}

				payment_transfer = client.payment.transfer(transaction_id, data=param)
				transfer = payment_transfer.get("items")[0]
				transfer_id = transfer.get("id")
				frappe.db.sql('''update `tabVendor Orders` set transaction_id=%(transferid)s where name=%(vendor_orderid)s''',{"transferid":transfer_id,"vendor_orderid":vendor_order.name})
	else:
		if gateway_settings.get('routing_enable') == 1:
			if gateway_settings.account_id != '':
				order_id = order_info.name
				if check_domain('saas'):
					check_order = frappe.db.get_all('Vendor Orders', filters={'order_reference': order_id})
					if check_order:
						order_id = check_order[0].name
				order_total=order_info.total_amount * (100 - gateway_settings.commission_percentage) / 100
				amount = int(order_total * 100)
				BillingAddress = order_info.first_name+" "+order_info.last_name+","+order_info.address+","+order_info.city+","+order_info.state+","+order_info.zipcode+"-"+order_info.country+","+order_info.phone
				ShippingAddress = order_info.shipping_first_name+"  "+order_info.shipping_last_name+","+order_info.shipping_shipping_address+","+order_info.shipping_city+","+order_info.shipping_state+","+order_info.shipping_zipcode+"-"+order_info.shipping_country+","+order_info.shipping_phone
				Notes = {"Customer Name":order_info.customer_name,"Customer Email":order_info.customer_email,"OrderId":order_id,"Billing Address":BillingAddress,"Shipping Address":ShippingAddress,"PaymentId":transaction_id}
				DATA = {'amount':amount,'currency':'INR','account':gateway_settings.account_id,"notes":Notes}
				param = {
	            	'transfers': {
	                	'currency': {
	                    	'amount': amount,
	                    	'currency': 'INR',
	                    	'account': gateway_settings.account_id,
	                    	'notes':Notes,
	                    	"linked_account_notes":["Customer Name","Customer Email","OrderId","Billing Address","Shipping Address","PaymentId"],
	                   
	                	}
	            	}
	       		}
				payment_transfer = client.payment.transfer(transaction_id, data=param)
				transfer = payment_transfer.get("items")[0]
				transfer_id = transfer.get("id")
				from ecommerce_business_store.accounts.api import make_payment as _make_payment
				_make_payment(order=order_info.name, mode_of_payment='Razor Pay', amount=order_info.outstanding_amount)
				submit_order=get_settings_value_from_domain('Order Settings','submit_order')
				if submit_order:
					order_info = frappe.get_doc(order_info.doctype, order_info.name) 
					order_info.docstatus = 1
					# order_info.payment_status='Paid'
					# order_info.outstanding_amount = 0	
					order_info.paid_amount = order_info.total_amount
					order_info.transaction_id = transfer_id
					order_info.save(ignore_permissions=True)

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
