from odoo import models, fields, api
from odoo.exceptions import ValidationError


class StockAlertRule(models.Model):
    _name = 'stock.alert.rule'
    _description = 'Stock Alert & Reorder Rule'
    _order = 'product_id, categ_id'

    name = fields.Char(string='Rule name', required=True)

    product_id = fields.Many2one('product.product', string='Product', ondelete='cascade')
    categ_id = fields.Many2one('product.category', string='Product Category', ondelete='cascade')

    min_qty = fields.Float(string='Minimum Quantity', required=True, default=0.0, help='Alert triggers when stock falls at or below this quantity.')
    reorder_qty = fields.Float(string='Reorder Quantity', required=True, default=1.0, help='Quantity to include in the auto-generated purchase order.')

    active = fields.Boolean(default=True)
    alert_email = fields.Char(string='Alert Email', help="Comma-separated email addresses to notify. Leave empty to skip email.")
    auto_purchase = fields.Boolean(string='Auto-Create PO', default=False, help="Automatically draft a purchase order when stock is critical.")
    location_id = fields.Many2one('stock.location', string='Stock Location', domain=[('usage', '=', 'internal')], help="Restrict check to a specific warehouse location.")

    @api.constrains('product_id', 'categ_id')
    def _check_scope(self):
        for rule in self:
            if not rule.product_id and not rule.categ_id:
                raise ValidationError('Each rule must target either a Product or a Product Category.')
            if rule.product_id and rule.categ_id:
                raise ValidationError('A rule cannot target both a Product and a Category at the same time.')

    @api.constrains('min_qty', 'reorder_qty')
    def _check_quantities(self):
        for rule in self:
            if rule.min_qty < 0:
                raise ValidationError('Minimum Quantity cannot be negative.')
            if rule.reorder_qty <= 0:
                raise ValidationError('Reorder Quantity must be greater than zero.')

    @api.model
    def _get_critical_rules(self):
        active_rules = self.search([('active', '=', True)])
        if not active_rules:
            return []

        categ_ids = active_rules.filtered('categ_id').mapped('categ_id').ids
        categ_product_map = {}

        if categ_ids:
            products_in_categs = self.env['product.product'].search([
                ('categ_id', 'in', categ_ids),
                ('active', '=', True),
            ])
            for p in products_in_categs:
                categ_product_map.setdefault(p.categ_id, []).append(p.id)

        rule_product_map = {}
        for rule in active_rules:
            if rule.product_id:
                rule_product_map[rule.id] = [rule.product_id.id]
            elif rule.categ_id:
                rule_product_map[rule.id] = categ_product_map.get(
                    rule.categ_id.id, []
                )

        all_product_ids = list(
            {pid for pids in rule_product_map.values() for pid in pids}
        )
        if not all_product_ids:
            return []

        internal_location_ids = self.env['stock.location'].search(
            [('usage', '=', 'internal')]
        ).ids

        quant_groups = self.env['stock.quant'].read_group(
            domain=[
                ('product_id', 'in', all_product_ids),
                ('location_id', 'in', internal_location_ids),
            ],
            fields=['product_id', 'location_id', 'quantity:sum'],
            groupby=['product_id', 'location_id'],
            lazy=False,
        )

        qty_by_product_location = {}
        qty_by_product = {}

        for row in quant_groups:
            pid = row['product_id'][0]
            lid = row['location_id'][0]
            qty = row['quantity'] or 0.0
            qty_by_product_location[(pid, lid)] = qty
            qty_by_product[pid] = qty_by_product.get(pid, 0.0) + qty

        critical = []
        for rule in active_rules:
            for pid in rule_product_map.get(rule.id, []):
                if rule.location_id:
                    qty = qty_by_product_location.get(
                        (pid, rule.location_id.id), 0.0
                    )
                else:
                    qty = qty_by_product.get(pid, 0.0)

                if qty<= rule.min_qty:
                    critical.append({
                        'rule': rule,
                        'product_id': pid,
                        'qty_on_hand': qty,
                    })

        return critical

    @api.model
    def _check_and_log(self):
        critical_items = self._get_critical_rules()
        if not critical_items:
            return

        today = fields.Date.today()

        existing_logs = self.env['stock.alert.log'].search([
            ('date', '=', today),
        ])
        already_logged = {
            (log.rule_id.id, log.product_id.id)
            for log in existing_logs
        }

        logs_to_create = []
        for item in critical_items:
            key = (item['rule'].id, item['product_id'])
            if key not in already_logged:
                logs_to_create.append({
                    'rule_id': item['rule'].id,
                    'product_id': item['product_id'],
                    'qty_on_hand': item['qty_on_hand'],
                    'min_qty': item['rule'].min_qty,
                    'date': today,
                    'state': 'alerted',
                })

        if logs_to_create:
            new_logs = self.env['stock.alert.log'].create(logs_to_create)
            new_logs.action_send_alert_email()
            new_logs.action_create_po()

    def action_test_detection(self):
        results = self.env['stock.alert.rule']._get_critical_rules()
        product_names = []
        for item in results:
            product = self.env['product.product'].browse(item['product_id'])
            product_names.append(
                f"{product.display_name} (qty: {item['qty_on_hand']})"
            )
        message = '\n'.join(product_names) if product_names else 'No critical stock found.'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Critical Stock Detection Results',
                'message': message,
                'type': 'warning' if product_names else 'success',
                'sticky': True,
            },
        }

    @api.model
    def get_dashboard_data(self):
        critical_items = self._get_critical_rules()
        result = []
        for item in critical_items:
            product = self.env['product.product'].browse(item['product_id'])
            result.append({
                'product_name': product.display_name,
                'qty_on_hand': item['qty_on_hand'],
                'min_qty': item['rule'].min_qty,
                'rule_name': item['rule'].name,
                'reorder_qty': item['rule'].reorder_qty,
            })
        return result