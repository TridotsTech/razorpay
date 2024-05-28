frappe.ui.form.on('Order', {
    refresh: function(frm) {
        if(frm.check_order_settings.generate_payment_link==1){
            if(frm.doc.payment_status!="Paid" && frm.doc.docstatus==1 ){
           
                        frm.add_custom_button("Generate Payment Link", function() {
                            frappe.call({
                            method: "razor_pay.razor_pay.api.generate_payment_link",
                            args: {
                                order_id: frm.doc.name
                            },
                            async:false,
                            callback: function(data) {
                                if(data.message.status=="Success")
                                {
                                    frappe.msgprint("Payment Links are sent to customer.")
                                }
                                else{
                                    frappe.msgprint("Payment Links are sent to customer.")
                                }

                            }
                         });
                        });
                    }
                    else{
                        // frappe.msgprint(r.message.message)
                    }
                }
        
        
    }
});