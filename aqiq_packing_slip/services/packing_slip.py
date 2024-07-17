import frappe
from frappe import _
from frappe.model import no_value_fields
from frappe.model.document import Document
from frappe.utils import cint, flt
from erpnext.stock.doctype.packing_slip.packing_slip import  PackingSlip

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
        
@frappe.whitelist()
def get_items(this_doc):
    self=frappe.get_doc("Packing Slip",this_doc)
    self.set("items", [])

    custom_fields = frappe.get_meta("Delivery Note Item").get_custom_fields()

    dn_details = get_details_for_packing(self)[0]
    print(dn_details)
    for item in dn_details:
        if flt(item.qty) > flt(item.packed_qty):
            ch = self.append('items', {})
            ch.item_code = item.item_code
            ch.item_name = item.item_name
            ch.stock_uom = item.stock_uom
            ch.description = item.description
            ch.batch_no = item.batch_no
            ch.qty = flt(item.qty) - flt(item.packed_qty)

            # copy custom fields
            for d in custom_fields:
                if item.get(d.fieldname):
                    ch.set(d.fieldname, item.get(d.fieldname))

    if not self.from_case_no:
        self.from_case_no = self.get_recommended_case_no()

    for d in self.items:
        res = frappe.db.get_value("Item", d.item_code,
            ["weight_per_unit", "weight_uom"], as_dict=True)

        if res and len(res)>0:
            d.net_weight = res["weight_per_unit"]
            d.weight_uom = res["weight_uom"]
    return dn_details,
            
def get_details_for_packing(self):
    """
        Returns
        * 'Delivery Note Items' query result as a list of dict
        * Item Quantity dict of current packing slip doc
        * No. of Cases of this packing slip
    """

    rows = [d.item_code for d in self.items]

    # also pick custom fields from delivery note
    custom_fields = ', '.join('dni.`{0}`'.format(d.fieldname)
        for d in frappe.get_meta("Delivery Note Item").get_custom_fields()
        if d.fieldtype not in no_value_fields)

    if custom_fields:
        custom_fields = ', ' + custom_fields

    condition = ""
    if rows:
        condition = " and item_code in (%s)" % (", ".join(["%s"]*len(rows)))

    # gets item code, qty per item code, latest packed qty per item code and stock uom
    res = frappe.db.sql("""
        SELECT 
            dni.item_code, 
            SUM(dni.qty) AS qty,
            i.weight_per_unit, 
            i.weight_uom,
            (
                SELECT 
                    SUM(psi.qty * (ABS(ps.to_case_no - ps.from_case_no) + 1))
                FROM 
                    `tabPacking Slip` ps
                    INNER JOIN `tabPacking Slip Item` psi ON ps.name = psi.parent
                WHERE 
                    ps.docstatus = 1
                    AND ps.delivery_note = dni.parent
                    AND psi.item_code = dni.item_code
            ) AS packed_qty,
            dni.stock_uom, 
            dni.item_name, 
            dni.description, 
            dni.batch_no 
            {custom_fields}
        FROM 
            `tabDelivery Note Item` dni
            INNER JOIN `tabItem` i ON dni.item_code = i.name
        WHERE 
            dni.parent = %s 
            {condition}
        GROUP BY 
            dni.item_code
    """.format(condition=condition, custom_fields=custom_fields),
    tuple([self.delivery_note] + rows), as_dict=1)


    ps_item_qty = dict([[d.item_code, d.qty] for d in self.get("items")])
    no_of_cases = cint(self.to_case_no) - cint(self.from_case_no) + 1

    return res, ps_item_qty, no_of_cases
