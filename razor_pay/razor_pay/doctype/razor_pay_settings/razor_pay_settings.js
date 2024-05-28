// Copyright (c) 2019, Valiant and contributors
// For license information, please see license.txt

frappe.ui.form.on('Razor Pay Settings', {
	refresh: function(frm) {
		let txt = 'Generate Webhook Secret';
		if(frm.doc.webhook_secret) {
			txt = 'Regenerate Webhook Secret';
		}
		frm.add_custom_button(txt, () => {
			frm.call("generate_webhook_key").then(() => {
				frm.refresh();
			});
		});
	}
});
