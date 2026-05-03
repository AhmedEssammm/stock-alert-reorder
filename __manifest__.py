{
    'name': 'Stock Alert & Reorder',
    'version': '17.0.1.0.0',
    'summary': 'Monitor stock levels, trigger reorders, and send alerts',
    'author': 'Ahmed Essam',
    'category': 'Inventory',
    'depends': ['stock', 'purchase', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_alert_rule_views.xml',
        'views/stock_alert_log_views.xml',
        'views/stock_alert_dashboard_action.xml',
        'data/mail_template.xml',
        'data/ir_cron.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'stock_alert_reorder/static/src/js/stock_alert_dashboard.js',
            'stock_alert_reorder/static/src/xml/stock_alert_dashboard.xml',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}