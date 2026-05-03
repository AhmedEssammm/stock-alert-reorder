/** @odoo-module **/

import { registry } from "@web/core/registry";

import { useService } from "@web/core/utils/hooks";

import { Component, useState, onWillStart } from "@odoo/owl";


class StockAlertDashboard extends Component {

    setup() {
        this.orm = useService("orm");

        this.state = useState({
            items: [],
            loading: true,
        });

        onWillStart(async () => {
            await this.loadData();
        })
    }

    async loadData() {
        const data = await this.orm.call(
            "stock.alert.rule",
            "get_dashboard_data",
            [],
        );
        this.state.items = data;
        this.state.loading = false;
    }
}

StockAlertDashboard.template = "stock_alert_reorder.StockAlertDashboard";

registry.category("actions").add("stock_alert_dashboard", StockAlertDashboard);