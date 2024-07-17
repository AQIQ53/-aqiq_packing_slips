import frappe

@frappe.whitelist(allow_guest=True)
def packing_slip_on_submit(name):
    self = frappe.get_doc("Packing Slip", name)
    ste = frappe.new_doc("Stock Entry")
    ste.company = self.custom_company
    ste.stock_entry_type = "Material Issue"
    ste.packing_slip = self.name
    ste.custom_cost_center = self.get("custom_cost_center")
    ste.project = self.get("project")
    ste.items = []
    for d in self.custom_materials:
        is_stock_item = frappe.db.get_value("Item", d.item_code, "is_stock_item")
        if is_stock_item:
            ste.append(
                "items",
                {
                    "item_code": d.item_code,
                    "qty": d.qty,
                    "s_warehouse": d.warehouse,
                    "cost_center": self.custom_cost_center,
                },
            )

    if ste.items:
        ste.save(ignore_permissions=True)
        ste.submit()
        frappe.msgprint("Stock Entry (Material Issue) created #" + ste.name)
