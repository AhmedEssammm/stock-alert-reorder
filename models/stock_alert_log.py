from odoo import models, fields


class StockAlertLog(models.Model):
    _name = 'stock.alert.log'
    _description = 'Stock Alert Log'
    _order = 'date desc, id desc'
    _rec_name = 'product_id'
    _inherit = ['mail.thread']

    rule_id = fields.Many2one('stock.alert.rule', string='Alert Rule', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True, ondelete='cascade')
    qty_on_hand = fields.Float(string='Qty at Alert Time', digits='Product Unit of Measure')
    min_qty = fields.Float(string='Threshold at Alert Time', digits='Product Unit of Measure')
    date = fields.Date(string='Alert Date', default=fields.Date.today, required=True)
    state = fields.Selection([
        ('alerted', 'Alerted'),
        ('ordered', 'Ordered'),
    ], string='Status', default='alerted', required=True)

    def action_send_alert_email(self):
        template = self.env.ref(
            'stock_alert_reorder.email_template_stock_alert',
            raise_if_not_found=False,
        )
        if not template:
            return

        for log in self:
            if not log.rule_id.alert_email:
                continue
            import logging
            _logger = logging.getLogger(__name__)
            _logger.info(
                "ALERT EMAIL: Would send to %s for product %s",
                log.rule_id.alert_email,
                log.product_id.display_name,
            )
            template.send_mail(
                log.id,
                email_values={'email_to': log.rule_id.alert_email},
                force_send=True,
            )

    def action_create_po(self):
        PurchaseOrder = self.env['purchase.order']
        PurchaseOrderLine = self.env['purchase.order.line']

        for log in self:
            if log.state == 'ordered':
                continue

            if not log.rule_id.auto_purchase:
                continue

            product = log.product_id
            rule = log.rule_id

            supplier_info = self.env['product.supplierinfo'].search([
                ('product_tmpl_id', '=', product.product_tmpl_id.id),
            ], order='sequence asc', limit=1)

            if not supplier_info:
                import logging
                _logger = logging.getLogger(__name__)
                _logger.warning(
                    "Stock Alert: No vendor found for product %s (rule: %s). "
                    "Skipping PO creation.",
                    product.display_name,
                    rule.name,
                )
                continue

            vendor = supplier_info.partner_id

            po = PurchaseOrder.create({
                'partner_id': vendor.id,
                'origin': f"Stock Alert: {rule.name}",
                'state': 'draft',
            })

            PurchaseOrderLine.create({
                'order_id': po.id,
                'product_id': product.id,
                'product_qty': rule.reorder_qty,
                'price_unit': supplier_info.price or 0.0,
                'date_planned': fields.Datetime.now(),
                'name': product.display_name,
                'product_uom': product.uom_po_id.id or product.uom_id.id,
            })

            log.state = 'ordered'