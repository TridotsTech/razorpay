from __future__ import unicode_literals
import frappe
import razorpay
from ecommerce_business_store.utils.setup import get_settings_value_from_domain, get_settings_from_domain
from frappe.utils import cstr, flt, getdate, nowdate, now, today, encode,date_diff, \
get_url, get_datetime, to_timedelta, add_days

@frappe.whitelist(allow_guest=True)
def create_payment_link_page(dt,docname,amount=0):
	try:
		gateway_settings = frappe.get_single('Razor Pay Settings')
		if gateway_settings.api_key and gateway_settings.api_secret:
			client = razorpay.Client(auth=(gateway_settings.api_key, gateway_settings.api_secret))
			customer_name = ""
			customer_email = ""
			customer_phone = ""
			customer = ""
			amount = amount
			amount_paid = 0
			catalog_settings = get_settings_from_domain('Catalog Settings')
			doc = frappe.get_doc(dt,docname)
			if dt == "Sales Invoice":
				customer_name = doc.customer_name
				customer_email = doc.customer_email
				customer_phone = doc.phone
				customer = doc.customer
				amount = int(frappe.db.get_value("Order",doc.reference,"outstanding_amount")*100) if not amount else int(amount*100)
				amount_paid = frappe.db.get_value("Order",doc.reference,"outstanding_amount") if not amount else amount
				if frappe.db.get_value("Sales Invoice",docname,"status")=="Paid":
					return {"status":"Failed","message":"Already payment is done for this invoice."}
			if dt == "Wallet Transaction":
				customer_name = frappe.db.get_value("Customers",doc.party,"full_name")
				customer_email = frappe.db.get_value("Customers",doc.party,"email")
				customer_phone = frappe.db.get_value("Customers",doc.party,"phone")
				customer = doc.party
				amount = int(doc.amount*100) if not amount else int(amount*100)
				amount_paid = doc.amount if not amount else amount
			if dt == "Order":
				customer_name = doc.customer_name
				customer_email = doc.customer_email
				customer_phone = doc.phone
				customer = doc.customer
				amount = int(doc.outstanding_amount*100) if not amount else int(amount*100)
				amount_paid = doc.outstanding_amount if not amount else amount
				if frappe.db.get_value("Order",docname,"payment_status")=="Paid":
					return {"status":"Failed","message":"Already payment is done for this order."}
			if customer and dt == "Order":
				cms_settings = frappe.get_single('CMS Settings')
				p_link = frappe.new_doc("Payment Link")
				p_link.reference_document = dt
				p_link.reference_name = docname
				p_link.payment_link = cms_settings.domain+"profile?my_account=orderdetail&order_id="+dt
				p_link.customer = customer
				p_link.payment_link_id = cms_settings.domain+"profile?my_account=orderdetail&order_id="+dt
				p_link.amount = amount_paid
				p_link.save(ignore_permissions=True)
				return {"status":"Success","message":"Payment link has been sent to customer.","url":response.get("short_url")}
			else:
				return {"status":"Failed","message":"Page is not available."}
	except Exception as e:
		frappe.log_error(message = frappe.get_traceback(),
						title="create_payment_link_page")
		return {"status":"Failed"}


@frappe.whitelist(allow_guest=True)
def create_payment_link(dt,docname,amount=0):
	try:
		gateway_settings = frappe.get_single('Razor Pay Settings')
		if gateway_settings.api_key and gateway_settings.api_secret:
			client = razorpay.Client(auth=(gateway_settings.api_key, gateway_settings.api_secret))
			customer_name = ""
			customer_email = ""
			customer_phone = ""
			customer = ""
			amount = amount
			amount_paid = 0
			customer_payment = amount
			catalog_settings = get_settings_from_domain('Catalog Settings')
			doc = frappe.get_doc(dt,docname)
			if dt == "Sales Invoice":
				customer_name = doc.customer_name
				customer_email = doc.customer_email
				customer_phone = doc.phone
				customer = doc.customer
				amount = int(frappe.db.get_value("Order",doc.reference,"outstanding_amount")*100) if not amount else int(amount*100)
				amount_paid = frappe.db.get_value("Order",doc.reference,"outstanding_amount") if not customer_payment else customer_payment
				if frappe.db.get_value("Sales Invoice",docname,"status")=="Paid":
					return {"status":"Failed","message":"Already payment is done for this invoice."}
			if dt == "Wallet Transaction":
				customer_name = frappe.db.get_value("Customers",doc.party,"full_name")
				customer_email = frappe.db.get_value("Customers",doc.party,"email")
				customer_phone = frappe.db.get_value("Customers",doc.party,"phone")
				customer = doc.party
				amount = int(doc.amount*100) if not amount else int(amount*100)
				amount_paid = doc.amount if not customer_payment else customer_payment
			if dt == "Order":
				customer_name = doc.customer_name
				customer_email = doc.customer_email
				customer_phone = doc.phone
				customer = doc.customer
				amount = int(doc.outstanding_amount*100) if not amount else int(amount*100)
				amount_paid = doc.outstanding_amount if not customer_payment else customer_payment
				if frappe.db.get_value("Order",docname,"payment_status")=="Paid":
					return {"status":"Failed","message":"Already payment is done for this order."}
			response = client.payment_link.create({
				"amount": amount,
				"currency": catalog_settings.default_currency,
				"accept_partial": False,
				"description": "Payment Against "+dt+" ( "+docname+" )",
				"customer": {
					"name": customer_name,
					"email": customer_email,
					"contact": customer_phone
				},
				"notify": {
					"sms": True,
					"email": True
				},
				"reminder_enable": True,
				"callback_url": frappe.utils.get_url()+"/api/method/razor_pay.razor_pay.api.complete_payment_link",
				"callback_method": "get"
			})
			if not response.get("error"):
				if customer:
					p_link = frappe.new_doc("Payment Link")
					p_link.reference_document = dt
					p_link.reference_name = docname
					p_link.payment_link = response.get("short_url")
					p_link.customer = customer
					p_link.payment_link_id = response.get("id")
					p_link.amount = amount_paid
					p_link.save(ignore_permissions=True)
					return {"status":"Success","message":"Payment link has been sent to customer.","url":response.get("short_url")}
			else:
				frappe.log_error(title="payment_link",message=response)
				return {"status":"Failed","message":response.get("error").get("description")}
	except Exception as e:
		frappe.log_error(message = frappe.get_traceback(),
						title="create_payment_link-Razorpay")
		return {"status":"Failed"}


@frappe.whitelist(allow_guest=True)
def create_payment_link_qrcode(dt,docname):
	payment_link = create_payment_link(dt,docname)
	if payment_link.get("status") == "Success":
		import qrcode
		from qrcode.image.pure import PymagingImage
		from frappe.utils import touch_file
		import json, math, os
		qr = qrcode.QRCode(
			version=1,
			error_correction=qrcode.constants.ERROR_CORRECT_L,
			box_size=10,
			border=4,
		)
		qr.add_data(payment_link.get("url"))
		qr.make(fit=True)
		img = qr.make_image(fill_color="black", back_color="white")
		filename = randomStringDigits(18)
		path = 'public/files/{filename}.png'.format(filename=filename)
		touch_file(os.path.join(frappe.get_site_path(),path))
		img.save(os.path.join(frappe.get_site_path(),path))
		return {"status":"Success","qr_code_url": frappe.utils.get_url()+"/files/" + filename + ".png"}

	else:
		return payment_link
@frappe.whitelist(allow_guest=True)
def create_payment_qrcode(dt,docname,amount=0):
	try:
		gateway_settings = frappe.get_single('Razor Pay Settings')
		if gateway_settings.api_key and gateway_settings.api_secret:
			customer = None
			amount = amount
			doc = frappe.get_doc(dt,docname)
			if dt == "Sales Invoice":
				customer = doc.customer
				amount = int(doc.outstanding_amount*100) if not amount else int(amount*100)
			if dt == "Order":
				customer = doc.customer
				amount = int(doc.outstanding_amount*100) if not amount else int(amount*100)
			if dt == "Wallet Transaction":
				customer = doc.party
				amount = int(doc.amount*100) if not amount else int(amount*100)
			if customer:
				# customer_obj = get_customer(gateway_settings,customer)
				# if customer_obj.get("status")=="Success":
				client = razorpay.Client(auth=(gateway_settings.api_key, gateway_settings.api_secret))
				qr_resp = client.qrcode.create({
				  "type": "upi_qr",
				  "usage": "single_use",
				  "fixed_amount": True,
				  "payment_amount": amount,
				  "description": "Payment Against "+dt+" ( "+docname+" )",
				})
				if not qr_resp.get("error"):
					p_link = frappe.new_doc("QR Code Link")
					p_link.reference_document = dt
					p_link.reference_name = docname
					p_link.payment_link = qr_resp.get("image_url")
					p_link.customer = customer
					p_link.payment_link_id = qr_resp.get("id")
					p_link.amount = amount/100
					p_link.save(ignore_permissions=True)
					frappe.db.commit()
					return {"status":"Success","qr_code_url":qr_resp.get("image_url")}
				else:
					return {"status":"Failed","message":qr_resp.get("error").get("description")}

			else:
				return {"status":"Failed","message":"No customer found."}
	except Exception as e:
		frappe.log_error(message = frappe.get_traceback(),
						title="create_payment_qrcode-Razorpay")
		return {"status":"Failed"}
def get_customer(gateway_settings,customer):
	client = razorpay.Client(auth=(gateway_settings.api_key, gateway_settings.api_secret))
	customer_name = frappe.db.get_value("Customers",doc.party,"full_name")
	customer_email = frappe.db.get_value("Customers",doc.party,"email")
	customer_phone = frappe.db.get_value("Customers",doc.party,"phone")
	customer_info = client.customer.create({
	  "name": customer_name,
	  "contact": customer_phone,
	  "email": customer_email,
	  "fail_existing": 0,
	})
	return {"status":"Success","customer_info":customer_info}
def randomStringDigits(stringLength=6):
	import random
	import string
	lettersAndDigits = string.ascii_uppercase + string.digits
	return ''.join(random.choice(lettersAndDigits) for i in range(stringLength))

@frappe.whitelist(allow_guest=True)
def complete_payment_link(**kwargs):
	response = kwargs
	if response.get("razorpay_payment_link_status")=="paid":
		payment_link = frappe.db.get_all("Payment Link",filters={"payment_link_id":response.get("razorpay_payment_link_id")})
		if payment_link:
			p_doc = frappe.get_doc("Payment Link",payment_link[0].name)
			frappe.local.response["type"] = "redirect"
			frappe.local.response["location"] = p_doc.payment_link	
	# try:
	# 	response = kwargs
	# 	frappe.log_error(title="complete_payment_link",message=response)
	# 	if response.get("razorpay_payment_link_status")=="paid":
	# 		payment_link = frappe.db.get_all("Payment Link",filters={"payment_link_id":response.get("razorpay_payment_link_id")})
	# 		if payment_link:
	# 			p_doc = frappe.get_doc("Payment Link",payment_link[0].name)
	# 			p_doc.payment_status = "Paid"
	# 			p_doc.transaction_id = response.get("razorpay_payment_id")
	# 			p_doc.save(ignore_permissions=True)
	# 			frappe.db.commit()
	# 			# frappe.log_error(title="payment link",message=p_doc.as_dict())
	# 			if p_doc.reference_document == "Sales Invoice":
	# 				from ecommerce_business_store.accounts.api import make_invoice_payment
	# 				pe = make_invoice_payment(source_name=p_doc.reference_name, mode_of_payment='Razor Pay', amount=p_doc.amount,transaction_id=response.get("razorpay_payment_id"))
	# 				pe.flags.ignore_permissions=True
	# 				pe.submit()
	# 				ref_doc = frappe.get_doc(p_doc.reference_document,p_doc.reference_name)
	# 				ref_doc.status = "Paid"  if flt(p_doc.amount)>=flt(ref_doc.total_amount) else "Partially Paid"
	# 				ref_doc.save(ignore_permissions=True)
	# 				# frappe.log_error(title="sales invoice",message=ref_doc.as_dict())
	# 				if ref_doc.reference:
	# 					if frappe.db.exists("Order",ref_doc.reference):
	# 						order_doc = frappe.get_doc("Order",ref_doc.reference)
	# 						# frappe.log_error(title="order enter",message=order_doc.as_dict())
	# 						if order_doc.transaction_id:
	# 							order_doc.transaction_id = order_doc.transaction_id+","+response.get("razorpay_payment_id")
	# 						else:
	# 							order_doc.transaction_id = response.get("razorpay_payment_id")
	# 						if order_doc.status == "Delivered" and order_doc.payment_status=="Paid":
	# 							order_doc.status="Completed"
	# 						order_doc.save(ignore_permissions=True)
	# 						frappe.db.commit()
	# 					if frappe.db.exists("Vendor Orders",ref_doc.reference) :
	# 						order_doc = frappe.get_doc("Order",ref_doc.reference)
	# 						if order_doc.status == "Delivered" and order_doc.payment_status=="Paid":
	# 							order_doc.status="Completed"
	# 							order_doc.save(ignore_permissions=True)
	# 							frappe.db.commit()
	# 				check_shipments = frappe.db.get_all("Shipment",filters={"reference_sales_invoice":p_doc.reference_name})
	# 				# frappe.log_error(title="check_shipments",message=check_shipments)
	# 				if check_shipments:
	# 					shipment = frappe.get_doc("Shipment",check_shipments[0].name)
	# 					shipment.payment_status = "Paid" if flt(p_doc.amount)>=flt(ref_doc.outstanding_amount) else "Partially Paid"
	# 					shipment.save(ignore_permissions=True)
	# 				frappe.publish_realtime('payment_link_complete', {})
	# 			if p_doc.reference_document == "Order":
	# 				from ecommerce_business_store.accounts.api import make_payment as _make_payment
	# 				payment_entry_name = _make_payment(order=p_doc.reference_name, mode_of_payment='Razor Pay', amount=p_doc.amount)
	# 				if frappe.db.get_all("Payment Entry",filters={"payment_entry_name":payment_entry_name}):
	# 					frappe.db.sql(f""" UPDATE `tabPayment Entry` SET payment_type='Receive' WHERE name='{payment_entry_name}' """)
	# 					frappe.db.commit()
	# 				if frappe.db.exists("Order",p_doc.reference_name):
	# 					order_doc = frappe.get_doc("Order",p_doc.reference_name)
	# 					if order_doc.transaction_id:
	# 						order_doc.transaction_id = order_doc.transaction_id+","+response.get("razorpay_payment_id")
	# 					else:
	# 						order_doc.transaction_id = response.get("razorpay_payment_id")
	# 					if order_doc.status == "Delivered" and order_doc.payment_status=="Paid":
	# 						order_doc.status="Completed"
	# 					order_doc.save(ignore_permissions=True)
	# 					frappe.db.commit()
	# 				frappe.publish_realtime('payment_link_complete', {})
	# 			if p_doc.reference_document == "Wallet Transaction":
	# 				w_trans = frappe.get_doc("Wallet Transaction",p_doc.reference_name)
	# 				w_trans.status = "Credited"
	# 				w_trans.transaction_type = "Pay"
	# 				w_trans.docstatus = 1
	# 				w_trans.transaction_id = response.get("razorpay_payment_id")
	# 				w_trans.save(ignore_permissions=True)
	# 				frappe.db.commit()
	# 				frappe.publish_realtime('payment_link_complete', {})
	# 			frappe.local.response["type"] = "redirect"
	# 			frappe.local.response["location"] = p_doc.payment_link	
	# except Exception as e:
	# 	frappe.log_error(message = frappe.get_traceback(),
	# 					title="complete_payment_link")			

@frappe.whitelist(allow_guest=True)
def payment_link_paid(**kwargs):
	try:
		response = kwargs.get("payload")
		frappe.log_error(title="payment_link_paid",message=response)
		allow = False
		payment_link_id = None
		if response and response.get("order").get("entity"):
			if response.get("order").get("entity").get("status")=="paid":
				if response.get("payment_link").get("entity"):
					allow = True
					payment_link_id = response.get("payment_link").get("entity").get("id")
					payment_transaction_id = response.get("payment").get("entity").get("id")
		if allow and payment_link_id:
			payment_link = frappe.db.get_all("Payment Link",filters={"payment_link_id":payment_link_id})
			if payment_link:
				p_doc = frappe.get_doc("Payment Link",payment_link[0].name)
				p_doc.payment_status = "Paid"
				p_doc.transaction_id = payment_transaction_id
				p_doc.save(ignore_permissions=True)
				frappe.db.commit()
				# frappe.log_error(title="payment link",message=p_doc.as_dict())
				if p_doc.reference_document == "Sales Invoice":
					from ecommerce_business_store.accounts.api import make_invoice_payment
					pe = make_invoice_payment(source_name=p_doc.reference_name, mode_of_payment='Razor Pay', amount=p_doc.amount,transaction_id=payment_transaction_id)
					pe.flags.ignore_permissions=True
					pe.submit()
					ref_doc = frappe.get_doc(p_doc.reference_document,p_doc.reference_name)
					ref_doc.status = "Paid"  if flt(p_doc.amount)>=flt(ref_doc.total_amount) else "Partially Paid"
					ref_doc.save(ignore_permissions=True)
					# frappe.log_error(title="sales invoice",message=ref_doc.as_dict())
					if ref_doc.reference:
						if frappe.db.exists("Order",ref_doc.reference):
							order_doc = frappe.get_doc("Order",ref_doc.reference)
							# frappe.log_error(title="order enter",message=order_doc.as_dict())
							if order_doc.transaction_id:
								order_doc.transaction_id = order_doc.transaction_id+","+payment_transaction_id
							else:
								order_doc.transaction_id = payment_transaction_id
							if order_doc.status == "Delivered" and order_doc.payment_status=="Paid":
								order_doc.status="Completed"
							order_doc.save(ignore_permissions=True)
							frappe.db.commit()
						if frappe.db.exists("Vendor Orders",ref_doc.reference) :
							order_doc = frappe.get_doc("Order",ref_doc.reference)
							if order_doc.status == "Delivered" and order_doc.payment_status=="Paid":
								order_doc.status="Completed"
								order_doc.save(ignore_permissions=True)
								frappe.db.commit()
					check_shipments = frappe.db.get_all("Shipment",filters={"reference_sales_invoice":p_doc.reference_name})
					# frappe.log_error(title="check_shipments",message=check_shipments)
					if check_shipments:
						shipment = frappe.get_doc("Shipment",check_shipments[0].name)
						shipment.payment_status = "Paid" if flt(p_doc.amount)>=flt(ref_doc.outstanding_amount) else "Partially Paid"
						shipment.save(ignore_permissions=True)
					frappe.publish_realtime('payment_link_complete', {})
				if p_doc.reference_document == "Order":
					from ecommerce_business_store.accounts.api import make_payment as _make_payment
					payment_entry_name = _make_payment(order=p_doc.reference_name, mode_of_payment='Razor Pay', amount=p_doc.amount)
					if frappe.db.get_all("Payment Entry",filters={"payment_entry_name":payment_entry_name}):
						frappe.db.sql(f""" UPDATE `tabPayment Entry` SET payment_type='Receive' WHERE name='{payment_entry_name}' """)
						frappe.db.commit()
					if frappe.db.exists("Order",p_doc.reference_name):
						order_doc = frappe.get_doc("Order",p_doc.reference_name)
						if order_doc.transaction_id:
							order_doc.transaction_id = order_doc.transaction_id+","+payment_transaction_id
						else:
							order_doc.transaction_id = payment_transaction_id
						if order_doc.status == "Delivered" and order_doc.payment_status=="Paid":
							order_doc.status="Completed"
						order_doc.save(ignore_permissions=True)
						frappe.db.commit()
					frappe.publish_realtime('payment_link_complete', {})
				if p_doc.reference_document == "Wallet Transaction":
					w_trans = frappe.get_doc("Wallet Transaction",p_doc.reference_name)
					w_trans.status = "Credited"
					w_trans.transaction_type = "Pay"
					w_trans.docstatus = 1
					w_trans.transaction_id = payment_transaction_id
					w_trans.save(ignore_permissions=True)
					frappe.db.commit()
					frappe.publish_realtime('payment_link_complete', {})
				
	except Exception as e:
		frappe.log_error(message = frappe.get_traceback(),
						title="complete_payment_link")		
@frappe.whitelist(allow_guest=True)
def complete_qrcode_payment(**kwargs):
	try:
		qrocde_resp = kwargs
		if qrocde_resp.get("payload"):
			if qrocde_resp.get("payload").get("payment"):
				if qrocde_resp.get("payload").get("payment").get("entity"):
					if qrocde_resp.get("payload").get("payment").get("entity").get("status")=="captured":
						transaction_id = qrocde_resp.get("payload").get("payment").get("entity").get("id")
						if qrocde_resp.get("payload").get("qr_code"):
							if qrocde_resp.get("payload").get("qr_code").get("entity"):
								qrcode_link = frappe.db.get_all("QR Code Link",filters={"payment_link_id":qrocde_resp.get("payload").get("qr_code").get("entity").get("id")})
								if qrcode_link:
									p_doc = frappe.get_doc("QR Code Link",qrcode_link[0].name)
									p_doc.payment_status = "Paid"
									p_doc.transaction_id = transaction_id
									p_doc.save(ignore_permissions=True)
									frappe.db.commit()
									if p_doc.reference_document == "Sales Invoice":
										from ecommerce_business_store.accounts.api import make_invoice_payment
										make_invoice_payment(source_name=p_doc.reference_name, mode_of_payment='Razor Pay', amount=p_doc.amount,transaction_id=transaction_id)
										ref_doc = frappe.get_doc(p_doc.reference_document,p_doc.reference_name)
										ref_doc.status = "Paid" if flt(p_doc.amount)>=flt(ref_doc.outstanding_amount) else "Partially Paid"
										ref_doc.save(ignore_permissions=True)
										if ref_doc.reference:
											if frappe.db.exists("Order",ref_doc.reference):
												order_doc = frappe.get_doc("Order",ref_doc.reference)
												if order_doc.transaction_id:
													order_doc.transaction_id = order_doc.transaction_id+","+transaction_id
												else:
													order_doc.transaction_id = transaction_id
												if order_doc.status == "Delivered" and order_doc.payment_status=="Paid":
													order_doc.status="Completed"
												order_doc.save(ignore_permissions=True)
												frappe.db.commit()
											if frappe.db.exists("Vendor Orders",ref_doc.reference) :
												order_doc = frappe.get_doc("Order",ref_doc.reference)
												if order_doc.status == "Delivered" and order_doc.payment_status=="Paid":
													order_doc.status="Completed"
													order_doc.save(ignore_permissions=True)
													frappe.db.commit()
										frappe.publish_realtime('payment_link_complete', {})
									if p_doc.reference_document == "Order":
										from ecommerce_business_store.accounts.api import make_payment as _make_payment
										_make_payment(order=op_doc.reference_name, mode_of_payment='Razor Pay', amount=p_doc.amount)
										if frappe.db.exists("Order",p_doc.reference_document):
											order_doc = frappe.get_doc("Order",p_doc.reference_document)
											if order_doc.transaction_id:
												order_doc.transaction_id = order_doc.transaction_id+","+transaction_id
											else:
												order_doc.transaction_id = response.get("razorpay_payment_id")
											if order_doc.status == "Delivered" and order_doc.payment_status=="Paid":
												order_doc.status="Completed"
											order_doc.save(ignore_permissions=True)
											frappe.db.commit()
										frappe.publish_realtime('payment_link_complete', {})
									if p_doc.reference_document == "Wallet Transaction":
										w_trans = frappe.get_doc("Wallet Transaction",p_doc.reference_name)
										w_trans.status = "Credited"
										w_trans.transaction_type = "Pay"
										w_trans.docstatus = 1
										w_trans.transaction_id = transaction_id
										w_trans.save(ignore_permissions=True)
										frappe.publish_realtime('payment_link_complete', {})
									frappe.local.response["type"] = "redirect"
									frappe.local.response["location"] = p_doc.payment_link

	except Exception as e:
		frappe.log_error(message = frappe.get_traceback(),
						title="complete_qrcode_payment")
@frappe.whitelist()
def generate_payment_link(order_id):
	return create_payment_link("Order",order_id)

@frappe.whitelist()
def check_invoices(order_id):
	sales_invoices = frappe.db.get_all("Sales Invoice",filters={"reference":order_id})
	if not sales_invoices:
		return {"status":"Failed","message":"No invoices found for this order."}
	return {"status":"Success"}

@frappe.whitelist()
def on_order_cancel(doc,method):
	try:
		gateway_settings = frappe.get_single('Razor Pay Settings')
		if gateway_settings.api_key and gateway_settings.api_secret:
			if gateway_settings.cancel_refund:
				client = razorpay.Client(auth=(gateway_settings.api_key, gateway_settings.api_secret))
				if doc.transaction_id:
					transaction_ids = doc.transaction_id.split(",")
					for x in transaction_ids:
						if x:
							payment_info = client.payment.fetch(x)
							if not payment_info.get("error_code"):
								client.payment.refund(x,{
								"amount":(doc.paid_amount*100),
								  "speed": "optimum",
								  "receipt": "Refund against the order - "+doc.name
								})
	except Exception as e:
		frappe.log_error(message = frappe.get_traceback(),
						title="razor_pay_on_order_cancel")


@frappe.whitelist()
def on_return_request_submit(doc,method):
	try:
		order_doc = frappe.get_doc("Order",doc.order_id)
		gateway_settings = frappe.get_single('Razor Pay Settings')
		if gateway_settings.api_key and gateway_settings.api_secret and doc.docstatus==1 and order_doc.paid_amount>0:
			# on 4/5/24 for homealankar
			# if gateway_settings.return_refund:
			if gateway_settings.return_refund and not doc.get("custom_refund_to",None):
			# end
				order_settings = get_settings_from_domain("Order Settings")
				item_filter = ','.join(['"' + x.get("product") + '"' for x in doc.get("items")])
				# and doc.is_rto==0
				if order_settings.return_amount_credited_to_wallet==0 and doc.is_refundable==1:
					pt_entries = []
					if not 'cars24_spare_parts' in frappe.get_installed_apps():
						pt_entries_query ="SELECT PE.paid_amount,PE.reference_no  FROM `tabPayment Entry` PE \
													INNER JOIN `tabPayment Reference` PR ON PE.name= PR.parent \
													WHERE PR.reference_name IN \
													 (SELECT SI.name FROM `tabSales Invoice` SI \
													 	INNER JOIN `tabSales Invoice Item` SII ON SII.parent = SI.name \
													 	WHERE SI.reference='{order_id}' AND (status='Paid' OR status='Partially Paid') AND SII.item IN({item_filter}) \
													 	AND SI.docstatus=1 GROUP BY SI.name) \
													 AND PE.docstatus=1 AND PE.mode_of_payment='Razor Pay' \
													 AND PE.payment_type='Receive' AND PE.party = '{customer_id}'".format(item_filter=item_filter,order_id=order_doc.name,customer_id=order_doc.customer)
						pt_entries= frappe.db.sql(pt_entries_query,as_dict=1)
						if not pt_entries:
							pt_entries_query ="SELECT PE.paid_amount,PE.reference_no  FROM `tabPayment Entry` PE \
													INNER JOIN `tabPayment Reference` PR ON PE.name= PR.parent \
													WHERE PR.reference_name= '{order_id}'\
													 AND PE.docstatus=1 AND PE.mode_of_payment='Razor Pay' \
													 AND PE.payment_type='Receive' AND PE.party = '{customer_id}'".format(order_id=order_doc.name,customer_id=order_doc.customer)
							frappe.log_error(title="pt_entries_query",message=pt_entries_query)
							pt_entries= frappe.db.sql(pt_entries_query,as_dict=1)
					ret_amt = 0
					for item in doc.items:
						price = frappe.db.get_value("Order Item",item.order_item,"price_with_tax")
						ret_amt += (item.quantity*price)
					amount_paid = 0
					frappe.log_error(f"ret_amt - {order_doc.name}",ret_amt)
					if pt_entries:
						for x in pt_entries:
							if x.reference_no:
								client = razorpay.Client(auth=(gateway_settings.api_key, gateway_settings.api_secret))
								payment_info = client.payment.fetch(x.reference_no)
								frappe.log_error(f"x.reference - {order_doc.name}",x.reference_no)
								frappe.log_error(f"payment_info - {order_doc.name}",payment_info)
								# if flt(payment_info.get("amount")/100)>=flt(ret_amt):
								ref_amount = 0
								actual_amt = flt(payment_info.get("amount")/100)
								frappe.log_error(f"actual_amt - {order_doc.name}",actual_amt)
								if payment_info.get("amount_refunded"):
									ref_amount = payment_info.get("amount_refunded")/100
									frappe.log_error(f"ref_amount - {order_doc.name}",ref_amount)
								if not payment_info.get("error_code"):
									if (flt(actual_amt)-flt(ref_amount))>0:
										refund_amount = flt(actual_amt)-flt(ref_amount)
										frappe.log_error(f"refund_amount 1 - {order_doc.name}",refund_amount)
										# if flt(ret_amt)>flt(refund_amount):
										# 	refund_amount = flt(payment_info.get("amount"))/100
										if flt(refund_amount)>flt(ret_amt):
											refund_amount = ret_amt
										amount_paid += refund_amount
										frappe.log_error(f"refund_amount 2 - {order_doc.name}",refund_amount)
										client.payment.refund(x.reference_no,{
										  "amount": refund_amount*100,
										  "speed": "normal",
										  "receipt": "Refund against the Return Request - "+doc.name+"("+x.reference_no+")"
										  })
										ret_amt = ret_amt - refund_amount
										frappe.log_error(f"ret_amt 1 - {order_doc.name}",ret_amt)
										make_return_payment_entry(order_doc,refund_amount,x.reference_no,"Razor Pay")
					if ret_amt > 0:
						wl_amt = ret_amt
						frappe.log_error(f"ret_amt 2 - {order_doc.name}",ret_amt)
						refund_wallet(wl_amt,order_settings,doc,order_doc)
						frappe.enqueue("razor_pay.razor_pay.api.make_return_payment_entry",source=order_doc,amount=wl_amt,reference_no="",mode_of_payment="Cash")
	except Exception as e:
		frappe.log_error(message = frappe.get_traceback(),
						title="on_return_request_submit")
@frappe.whitelist()
def on_sales_invoice_cancel(doc,method):
	order_doc = frappe.get_doc("Order",doc.reference)
	gateway_settings = frappe.get_single('Razor Pay Settings')
	if gateway_settings.api_key and gateway_settings.api_secret and doc.paid_amount>0:
		if gateway_settings.return_refund:
			client = razorpay.Client(auth=(gateway_settings.api_key, gateway_settings.api_secret))
			order_settings = get_settings_from_domain("Order Settings")
			if order_settings.return_amount_credited_to_wallet==0:
				pt_entries_query ="SELECT PE.paid_amount,PE.reference_no  FROM `tabPayment Entry` PE \
											INNER JOIN `tabPayment Reference` PR ON PE.name= PR.parent \
											WHERE PR.reference_name =%(invoice_id)s \
											 AND PE.docstatus=1 AND PE.mode_of_payment='Razor Pay' \
											 AND PE.payment_type='Receive' AND PE.party = '{customer_id}'".format(invoice_id=doc.name,customer_id=order_doc.customer)
				pt_entries= frappe.db.sql(pt_entries_query,as_dict=1)
				ret_amt = doc.paid_amount
				amount_paid = 0
				if pt_entries:
					for x in pt_entries:
						if x.reference_no:
							payment_info = client.payment.fetch(x.reference_no)
							frappe.log_error("payment_info",payment_info)
							# if flt(payment_info.get("amount")/100)>=flt(ret_amt):
							ref_amount = 0
							if payment_info.get("amount_refunded"):
								ref_amount = payment_info.get("amount_refunded")/100
							if not payment_info.get("error_code"):
								if (flt(ret_amt)-flt(ref_amount))>0:
									refund_amount = flt(ret_amt)-flt(ref_amount)
									if flt(ret_amt)>flt(payment_info.get("amount")/100):
										refund_amount = flt(payment_info.get("amount"))/100
									amount_paid += refund_amount
									frappe.log_error("refund_amount",refund_amount)
									client.payment.refund(x.reference_no,{
									  "amount": refund_amount*100,
									  "speed": "optimum",
									  "receipt": "Refund against the Sales Invoice - "+doc.name
									  })
									make_return_payment_entry(order_doc,refund_amount,x.reference_no,"Razor Pay")
				if ret_amt > amount_paid:
					wl_amt = ret_amt - amount_paid
					refund_invoice_wallet(wl_amt,doc)
					frappe.enqueue("razor_pay.razor_pay.api.make_return_payment_entry",source=order_doc,amount=wl_amt,reference_no="",mode_of_payment="Cash")

def refund_invoice_wallet(ret_amt,doc):
	remaining_amt = 0
	amount_to_paid = ret_amt
	wl_trans = frappe.db.sql("""
							SELECT SUM(W.amount) AS t_amount FROM `tabWallet Transaction`  W
							WHERE order_type = 'Sales Invoice' AND 
							order_id =%(invoice_id)s AND
							status='Debited' AND docstatus=1
						 """,{"invoice_id":doc.name},as_dict=1)
	if wl_trans and wl_trans[0].t_amount:
		if ret_amt > wl_trans[0].t_amount:
			remaining_amt = ret_amt - wl_trans[0].t_amount
			amount_to_paid = wl_trans[0].t_amount
	if remaining_amt>0:
		pt_entries_query ="SELECT SUM(PE.paid_amount) AS paid_amount FROM `tabPayment Entry` PE \
									INNER JOIN `tabPayment Reference` PR ON PE.name= PR.parent \
									WHERE PR.reference_name =%(invoice_id)s\
									 AND PE.docstatus=1 AND PE.mode_of_payment='Cash' \
									 AND PE.payment_type='Receive' AND PE.party = '{customer_id}'".format(invoice_id=doc.name,customer_id=doc.customer)

		pt_entries= frappe.db.sql(pt_entries_query,as_dict=1)
		if pt_entries:
			if pt_entries[0].paid_amount>remaining_amt:
				amount_to_paid += remaining_amt

	wallet_doc = frappe.new_doc('Wallet Transaction')
	wallet_doc.type = "Customers"
	wallet_doc.party_type = "Customers"
	wallet_doc.party = doc.customer
	wallet_doc.reference = "Sales Invoice"
	wallet_doc.order_type = "Sales Invoice"
	wallet_doc.purpose_type = "Auto-Refund on cash orders"
	wallet_doc.order_id = doc.name
	wallet_doc.transaction_date = now()
	wallet_doc.total_value = amount_to_paid
	wallet_doc.transaction_type = "Pay"
	wallet_doc.is_settlement_paid = 1
	wallet_doc.amount = amount_to_paid
	wallet_doc.status = "Credited"
	wallet_doc.notes = "Against Sales Invoice: "+doc.name
	wallet_doc.flags.ignore_permissions = True
	wallet_doc.submit()
def refund_wallet(ret_amt,order_settings,doc,order_info):
	if order_settings.return_amount_credited_to_wallet==0 and doc.docstatus ==1 and order_info.payment_status!="Pending":
		amount_to_paid = ret_amt
		wallet_doc = frappe.new_doc('Wallet Transaction')
		wallet_doc.type = "Customers"
		wallet_doc.party_type = "Customers"
		wallet_doc.party = doc.customer
		wallet_doc.reference = "Order"
		wallet_doc.order_type = "Order"
		wallet_doc.purpose_type = "Auto-Refund on cash orders"
		wallet_doc.order_id = doc.order_id
		wallet_doc.transaction_date = now()
		wallet_doc.total_value = amount_to_paid
		wallet_doc.transaction_type = "Pay"
		wallet_doc.is_settlement_paid = 1
		wallet_doc.amount = amount_to_paid
		wallet_doc.status = "Credited"
		wallet_doc.notes = "Against Return Request: "+doc.name
		wallet_doc.flags.ignore_permissions = True
		wallet_doc.submit()

def make_return_payment_entry(source,amount,reference_no,mode_of_payment):
	default_currency = get_settings_from_domain('Catalog Settings')
	pe = frappe.new_doc("Payment Entry")
	pe.payment_type = 'Pay'
	# pe.cost_center = doc.get("cost_center")
	pe.posting_date = nowdate()
	pe.mode_of_payment = mode_of_payment
	pe.party_type = "Customers"
	pe.party = source.customer
	pe.party_name = source.customer_name
	pe.contact_person = ""
	pe.contact_email = ""
	pe.paid_amount = (amount)
	pe.base_paid_amount = (amount)
	pe.received_amount = (amount)
	pe.reference_no = reference_no
	paid_amount=amount
	pe.allocate_payment_amount = 1
	payment_type = 'received from'
	if pe.payment_type == 'Pay':
		payment_type = 'paid to'
	pe.remarks = 'Amount {0} {1} {2} {3}'.format(default_currency.default_currency, pe.paid_amount, payment_type, pe.party)
	pe.append("references", {
		'reference_doctype':"Order",
		'reference_name': source.name,
		"bill_no": "",
		"due_date": source.order_date,
		'total_amount': paid_amount,
		'outstanding_amount': paid_amount,
		'allocated_amount': paid_amount
	})
	pe.docstatus=1
	frappe.log_error(title="return outstanding",message=pe.references[0].outstanding_amount)
	pe.save(ignore_permissions=True)
	frappe.db.commit()

@frappe.whitelist()
def check_invoice_payment_status(invoice_id):
	return {"status":"Success","payment_status":frappe.db.get_value("Sales Invoice",invoice_id,"status"),"paid_amount":'%.2f' % frappe.db.get_value("Sales Invoice",invoice_id,"paid_amount")}
@frappe.whitelist()
def check_payment_status(order_id):
	return {"status":"Success","payment_status":frappe.db.get_value("Order",order_id,"payment_status")}