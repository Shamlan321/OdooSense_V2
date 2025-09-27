#!/usr/bin/env python3

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

@dataclass
class ReportTemplate:
    """Represents a report template"""
    name: str
    description: str
    model: str
    fields: List[str]
    domain: List = None
    group_by: List[str] = None
    order_by: str = ""
    chart_type: str = "table"
    date_field: str = ""
    
class OdooReportingService:
    """Service for generating reports and data summaries"""
    
    def __init__(self, odoo_client):
        self.odoo_client = odoo_client
        self.report_templates = self._build_report_templates()
        
    def _build_report_templates(self) -> Dict[str, ReportTemplate]:
        """Build predefined report templates"""
        return {
            "sales_performance": ReportTemplate(
                name="Sales Performance Report",
                description="Monthly sales performance by region/salesperson",
                model="sale.order",
                fields=["name", "partner_id", "user_id", "amount_total", "state", "date_order"],
                domain=[("state", "in", ["sale", "done"])],
                group_by=["user_id", "partner_id"],
                order_by="date_order desc",
                chart_type="bar",
                date_field="date_order"
            ),
            "inventory_snapshot": ReportTemplate(
                name="Inventory Levels Report",
                description="Current inventory levels and reorder points",
                model="stock.quant",
                fields=["product_id", "location_id", "quantity", "reserved_quantity"],
                domain=[("quantity", ">", 0)],
                group_by=["product_id", "location_id"],
                order_by="quantity asc",
                chart_type="table"
            ),
            "customer_360": ReportTemplate(
                name="Customer 360 View",
                description="Complete customer overview with orders, invoices, and tickets",
                model="res.partner",
                fields=["name", "email", "phone", "customer_rank", "supplier_rank"],
                domain=[("customer_rank", ">", 0)],
                group_by=[],
                order_by="name",
                chart_type="table"
            ),
            "hr_headcount": ReportTemplate(
                name="HR Headcount Report",
                description="Employee headcount breakdown by department",
                model="hr.employee",
                fields=["name", "department_id", "job_title", "work_email"],
                domain=[("active", "=", True)],
                group_by=["department_id"],
                order_by="department_id",
                chart_type="pie"
            ),
            "financial_summary": ReportTemplate(
                name="Financial Summary",
                description="Revenue, expenses, and profit overview",
                model="account.move",
                fields=["name", "partner_id", "amount_total", "state", "move_type", "invoice_date"],
                domain=[("state", "=", "posted")],
                group_by=["move_type"],
                order_by="invoice_date desc",
                chart_type="line",
                date_field="invoice_date"
            ),
            "crm_pipeline": ReportTemplate(
                name="CRM Pipeline Report",
                description="Sales pipeline and opportunity analysis",
                model="crm.lead",
                fields=["name", "partner_name", "expected_revenue", "probability", "stage_id", "user_id"],
                domain=[("type", "=", "opportunity")],
                group_by=["stage_id", "user_id"],
                order_by="expected_revenue desc",
                chart_type="funnel"
            ),
            "customer_summary": ReportTemplate(
                name="Customer Summary Report",
                description="Comprehensive customer summary with recent orders, outstanding invoices, and support tickets",
                model="res.partner",
                fields=["id", "name", "email", "phone", "street", "city", "country_id", "customer_rank"],
                domain=[("customer_rank", ">", 0)],
                group_by=[],
                order_by="name",
                chart_type="table"
            )
        }
    
    def generate_report(self, report_key: str, filters: Dict[str, Any] = None, 
                       date_range: Tuple[str, str] = None) -> Dict[str, Any]:
        """Generate a report based on template
        
        Args:
            report_key: Key of the report template
            filters: Additional filters to apply
            date_range: Date range tuple (start_date, end_date)
            
        Returns:
            Report data dictionary
        """
        try:
            if report_key not in self.report_templates:
                raise ValueError(f"Report template '{report_key}' not found")
            
            template = self.report_templates[report_key]
            domain = list(template.domain) if template.domain else []
            
            # Apply date range filter
            if date_range and template.date_field:
                start_date, end_date = date_range
                domain.extend([
                    (template.date_field, ">=", start_date),
                    (template.date_field, "<=", end_date)
                ])
            
            # Apply additional filters
            if filters:
                for field, value in filters.items():
                    if isinstance(value, list):
                        domain.append((field, "in", value))
                    else:
                        domain.append((field, "=", value))
            
            # Fetch data
            records = self.odoo_client.search_read(
                model=template.model,
                domain=domain,
                fields=template.fields
            )
            
            # Process data based on grouping
            if template.group_by:
                processed_data = self._group_data(records, template.group_by)
            else:
                processed_data = records
            
            return {
                "template": template,
                "data": processed_data,
                "total_records": len(records),
                "filters_applied": filters or {},
                "date_range": date_range,
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Report generation failed: {str(e)}")
            raise
    
    def _group_data(self, records: List[Dict], group_fields: List[str]) -> Dict[str, Any]:
        """Group data by specified fields
        
        Args:
            records: List of records
            group_fields: Fields to group by
            
        Returns:
            Grouped data dictionary
        """
        grouped = {}
        
        for record in records:
            # Create group key
            group_key_parts = []
            for field in group_fields:
                value = record.get(field)
                if isinstance(value, list) and len(value) > 1:
                    # Handle Many2one fields [id, name]
                    group_key_parts.append(str(value[1]))
                else:
                    group_key_parts.append(str(value))
            
            group_key = " - ".join(group_key_parts)
            
            if group_key not in grouped:
                grouped[group_key] = {
                    "records": [],
                    "count": 0,
                    "totals": {}
                }
            
            grouped[group_key]["records"].append(record)
            grouped[group_key]["count"] += 1
            
            # Calculate totals for numeric fields
            for field, value in record.items():
                if isinstance(value, (int, float)) and field not in ["id"]:
                    if field not in grouped[group_key]["totals"]:
                        grouped[group_key]["totals"][field] = 0
                    grouped[group_key]["totals"][field] += value
        
        return grouped
    
    def get_sales_performance(self, period: str = "month", region: str = None, 
                             salesperson: str = None) -> Dict[str, Any]:
        """Generate sales performance report
        
        Args:
            period: Time period (month, quarter, year)
            region: Specific region filter
            salesperson: Specific salesperson filter
            
        Returns:
            Sales performance data
        """
        # Calculate date range based on period
        end_date = datetime.now()
        if period == "month":
            start_date = end_date.replace(day=1)
        elif period == "quarter":
            quarter_start_month = ((end_date.month - 1) // 3) * 3 + 1
            start_date = end_date.replace(month=quarter_start_month, day=1)
        elif period == "year":
            start_date = end_date.replace(month=1, day=1)
        else:
            start_date = end_date - timedelta(days=30)
        
        filters = {}
        if region:
            # Assuming region is stored in partner's state_id
            filters["partner_id.state_id.name"] = region
        if salesperson:
            filters["user_id.name"] = salesperson
        
        return self.generate_report(
            "sales_performance",
            filters=filters,
            date_range=(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
        )
    
    def get_inventory_below_reorder(self, location: str = None) -> Dict[str, Any]:
        """Get inventory items below reorder point
        
        Args:
            location: Specific location filter
            
        Returns:
            Inventory data for items below reorder point
        """
        try:
            # Get products with reorder rules
            reorder_rules = self.odoo_client.search_read(
                model="stock.warehouse.orderpoint",
                domain=[],
                fields=["product_id", "product_min_qty", "location_id"]
            )
            
            # Get current stock levels
            domain = [("quantity", ">", 0)]
            if location:
                domain.append(("location_id.name", "=", location))
            
            stock_quants = self.odoo_client.search_read(
                model="stock.quant",
                domain=domain,
                fields=["product_id", "location_id", "quantity", "reserved_quantity"]
            )
            
            # Find items below reorder point
            below_reorder = []
            reorder_dict = {(rule["product_id"][0], rule["location_id"][0]): rule["product_min_qty"] 
                          for rule in reorder_rules}
            
            for quant in stock_quants:
                product_id = quant["product_id"][0]
                location_id = quant["location_id"][0]
                available_qty = quant["quantity"] - quant["reserved_quantity"]
                
                min_qty = reorder_dict.get((product_id, location_id), 0)
                if available_qty < min_qty:
                    below_reorder.append({
                        **quant,
                        "available_quantity": available_qty,
                        "min_quantity": min_qty,
                        "shortage": min_qty - available_qty
                    })
            
            return {
                "template": self.report_templates["inventory_snapshot"],
                "data": below_reorder,
                "total_records": len(below_reorder),
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Inventory reorder report failed: {str(e)}")
            raise
    
    def get_customer_360_view(self, customer_name: str) -> Dict[str, Any]:
        """Get comprehensive customer view
        
        Args:
            customer_name: Customer name or partial name
            
        Returns:
            Complete customer overview
        """
        try:
            # Find customer
            customers = self.odoo_client.search_read(
                model="res.partner",
                domain=[("name", "ilike", customer_name), ("customer_rank", ">", 0)],
                fields=["id", "name", "email", "phone", "street", "city", "country_id"]
            )
            
            if not customers:
                return {"error": f"Customer '{customer_name}' not found"}
            
            customer = customers[0]
            customer_id = customer["id"]
            
            # Get sales orders
            sales_orders = self.odoo_client.search_read(
                model="sale.order",
                domain=[("partner_id", "=", customer_id)],
                fields=["name", "date_order", "amount_total", "state"],
                limit=10
            )
            
            # Get invoices
            invoices = self.odoo_client.search_read(
                model="account.move",
                domain=[("partner_id", "=", customer_id), ("move_type", "=", "out_invoice")],
                fields=["name", "invoice_date", "amount_total", "state", "payment_state"],
                limit=10
            )
            
            # Get support tickets (if helpdesk module is installed)
            support_tickets = []
            try:
                support_tickets = self.odoo_client.search_read(
                    model="helpdesk.ticket",
                    domain=[("partner_id", "=", customer_id)],
                    fields=["name", "create_date", "stage_id", "priority"],
                    limit=5
                )
            except:
                # Helpdesk module not installed
                pass
            
            # Calculate summary statistics
            total_orders = len(sales_orders)
            total_revenue = sum(order["amount_total"] for order in sales_orders if order["state"] in ["sale", "done"])
            outstanding_invoices = [inv for inv in invoices if inv["payment_state"] != "paid"]
            outstanding_amount = sum(inv["amount_total"] for inv in outstanding_invoices)
            
            return {
                "customer": customer,
                "summary": {
                    "total_orders": total_orders,
                    "total_revenue": total_revenue,
                    "outstanding_invoices": len(outstanding_invoices),
                    "outstanding_amount": outstanding_amount,
                    "support_tickets": len(support_tickets)
                },
                "recent_orders": sales_orders,
                "recent_invoices": invoices,
                "support_tickets": support_tickets,
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Customer 360 view failed: {str(e)}")
            raise
    
    def get_hr_headcount(self, department: str = None) -> Dict[str, Any]:
        """Get HR headcount breakdown
        
        Args:
            department: Specific department filter
            
        Returns:
            HR headcount data
        """
        filters = {}
        if department:
            filters["department_id.name"] = department
        
        return self.generate_report("hr_headcount", filters=filters)
    
    def get_customer_summary(self, customer_name: str) -> Dict[str, Any]:
        """Generate comprehensive customer summary report
        
        Args:
            customer_name: Customer name or partial name to search for
            
        Returns:
            Customer summary with orders, invoices, and support tickets
        """
        try:
            # Find customer
            customers = self.odoo_client.search_read(
                model="res.partner",
                domain=[("name", "ilike", customer_name), ("customer_rank", ">", 0)],
                fields=["id", "name", "email", "phone", "street", "city", "country_id"]
            )
            
            if not customers:
                return {
                    "template": self.report_templates["customer_summary"],
                    "error": f"Customer '{customer_name}' not found",
                    "generated_at": datetime.now().isoformat()
                }
            
            customer = customers[0]
            customer_id = customer["id"]
            
            # Get recent sales orders (last 30 days)
            recent_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            recent_orders = self.odoo_client.search_read(
                model="sale.order",
                domain=[
                    ("partner_id", "=", customer_id),
                    ("date_order", ">=", recent_date)
                ],
                fields=["name", "date_order", "amount_total", "state"]
            )
            # Sort by date_order descending
            recent_orders.sort(key=lambda x: x.get("date_order", ""), reverse=True)
            
            # Get outstanding invoices
            outstanding_invoices = self.odoo_client.search_read(
                model="account.move",
                domain=[
                    ("partner_id", "=", customer_id),
                    ("move_type", "=", "out_invoice"),
                    ("payment_state", "!=", "paid"),
                    ("state", "=", "posted")
                ],
                fields=["name", "invoice_date", "amount_total", "amount_residual", "payment_state"]
            )
            # Sort by invoice_date descending
            outstanding_invoices.sort(key=lambda x: x.get("invoice_date", ""), reverse=True)
            
            # Get recent support tickets (if helpdesk module is available)
            support_tickets = []
            try:
                support_tickets = self.odoo_client.search_read(
                    model="helpdesk.ticket",
                    domain=[
                        ("partner_id", "=", customer_id),
                        ("create_date", ">=", recent_date)
                    ],
                    fields=["name", "create_date", "stage_id", "priority", "description"],
                    limit=10
                )
                # Sort by create_date descending
                support_tickets.sort(key=lambda x: x.get("create_date", ""), reverse=True)
            except Exception:
                # Helpdesk module not installed or accessible
                pass
            
            # Calculate summary metrics
            total_recent_orders = len(recent_orders)
            recent_order_value = sum(order["amount_total"] for order in recent_orders 
                                   if order["state"] in ["sale", "done"])
            total_outstanding = len(outstanding_invoices)
            outstanding_amount = sum(inv["amount_residual"] for inv in outstanding_invoices)
            open_tickets = len([ticket for ticket in support_tickets 
                              if ticket.get("stage_id") and "closed" not in str(ticket["stage_id"]).lower()])
            
            # Prepare comprehensive summary data
            summary_data = {
                "customer_info": customer,
                "metrics": {
                    "recent_orders_count": total_recent_orders,
                    "recent_orders_value": recent_order_value,
                    "outstanding_invoices_count": total_outstanding,
                    "outstanding_amount": outstanding_amount,
                    "open_support_tickets": open_tickets,
                    "total_support_tickets": len(support_tickets)
                },
                "recent_orders": recent_orders[:5],  # Show top 5 recent orders
                "outstanding_invoices": outstanding_invoices[:5],  # Show top 5 outstanding
                "support_tickets": support_tickets[:3]  # Show top 3 tickets
            }
            
            return {
                "template": self.report_templates["customer_summary"],
                "data": summary_data,
                "customer_name": customer["name"],
                "total_records": 1,
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Customer summary generation failed: {str(e)}")
            return {
                "template": self.report_templates["customer_summary"],
                "error": f"Failed to generate customer summary: {str(e)}",
                "generated_at": datetime.now().isoformat()
            }
    
    def format_report_response(self, report_data: Dict[str, Any]) -> str:
        """Format report data for user display
        
        Args:
            report_data: Report data dictionary
            
        Returns:
            Formatted report string
        """
        if "error" in report_data:
            return f"❌ **Error:** {report_data['error']}"
        
        template = report_data.get("template")
        data = report_data.get("data", [])
        total_records = report_data.get("total_records", 0)
        
        response = f"📊 **{template.name}**\n\n"
        response += f"📝 {template.description}\n\n"
        response += f"📈 **Total Records:** {total_records}\n"
        response += f"🕒 **Generated:** {report_data.get('generated_at', 'Unknown')}\n\n"
        
        if isinstance(data, dict):  # Grouped data
            response += "**Summary by Group:**\n\n"
            for group_name, group_data in data.items():
                response += f"🔹 **{group_name}**\n"
                response += f"   📊 Count: {group_data['count']}\n"
                
                # Show totals for numeric fields
                if group_data.get("totals"):
                    for field, total in group_data["totals"].items():
                        if field in ["amount_total", "expected_revenue"]:
                            response += f"   💰 {field.replace('_', ' ').title()}: ${total:,.2f}\n"
                        elif isinstance(total, (int, float)):
                            response += f"   📊 {field.replace('_', ' ').title()}: {total:,.0f}\n"
                response += "\n"
        
        elif isinstance(data, list):  # List data
            if data:
                response += "**Top Results:**\n\n"
                for i, record in enumerate(data[:5], 1):
                    name = record.get("name") or record.get("display_name", "Unknown")
                    response += f"{i}. **{name}**\n"
                    
                    # Show key fields
                    for field in ["amount_total", "quantity", "expected_revenue"]:
                        if field in record and record[field]:
                            value = record[field]
                            if field in ["amount_total", "expected_revenue"]:
                                response += f"   💰 {field.replace('_', ' ').title()}: ${value:,.2f}\n"
                            else:
                                response += f"   📊 {field.replace('_', ' ').title()}: {value:,.0f}\n"
                    response += "\n"
                
                if len(data) > 5:
                    response += f"... and {len(data) - 5} more records\n\n"
        
        return response
    
    def format_customer_360_response(self, customer_data: Dict[str, Any]) -> str:
        """Format customer 360 view for display
        
        Args:
            customer_data: Customer 360 data
            
        Returns:
            Formatted customer overview string
        """
        if "error" in customer_data:
            return f"❌ **Error:** {customer_data['error']}"
        
        customer = customer_data["customer"]
        summary = customer_data["summary"]
        
        response = f"👤 **Customer 360 View: {customer['name']}**\n\n"
        
        # Contact Information
        response += "📞 **Contact Information:**\n"
        response += f"   📧 Email: {customer.get('email', 'N/A')}\n"
        response += f"   📱 Phone: {customer.get('phone', 'N/A')}\n"
        if customer.get('street'):
            response += f"   🏠 Address: {customer['street']}"
            if customer.get('city'):
                response += f", {customer['city']}"
            response += "\n"
        response += "\n"
        
        # Summary Statistics
        response += "📊 **Summary Statistics:**\n"
        response += f"   🛒 Total Orders: {summary['total_orders']}\n"
        response += f"   💰 Total Revenue: ${summary['total_revenue']:,.2f}\n"
        response += f"   📄 Outstanding Invoices: {summary['outstanding_invoices']}\n"
        response += f"   💳 Outstanding Amount: ${summary['outstanding_amount']:,.2f}\n"
        response += f"   🎫 Support Tickets: {summary['support_tickets']}\n\n"
        
        # Recent Orders
        recent_orders = customer_data.get("recent_orders", [])
        if recent_orders:
            response += "🛒 **Recent Orders:**\n"
            for order in recent_orders[:3]:
                response += f"   • {order['name']} - ${order['amount_total']:,.2f} ({order['state']})\n"
            response += "\n"
        
        # Outstanding Invoices
        outstanding = [inv for inv in customer_data.get("recent_invoices", []) 
                      if inv.get("payment_state") != "paid"]
        if outstanding:
            response += "💳 **Outstanding Invoices:**\n"
            for invoice in outstanding[:3]:
                response += f"   • {invoice['name']} - ${invoice['amount_total']:,.2f} ({invoice['state']})\n"
            response += "\n"
        
        return response
    
    def format_customer_summary_response(self, summary_data: Dict[str, Any]) -> str:
        """Format customer summary report for display
        
        Args:
            summary_data: Customer summary data
            
        Returns:
            Formatted customer summary string
        """
        if "error" in summary_data:
            return f"❌ **Error:** {summary_data['error']}"
        
        data = summary_data["data"]
        customer = data["customer_info"]
        metrics = data["metrics"]
        
        response = f"📋 **Customer Summary: {customer['name']}**\n\n"
        
        # Contact Information
        response += "📞 **Contact Information:**\n"
        response += f"   📧 Email: {customer.get('email', 'N/A')}\n"
        response += f"   📱 Phone: {customer.get('phone', 'N/A')}\n"
        if customer.get('street'):
            response += f"   🏠 Address: {customer['street']}"
            if customer.get('city'):
                response += f", {customer['city']}"
            response += "\n"
        response += "\n"
        
        # Key Metrics
        response += "📊 **Key Metrics (Last 30 Days):**\n"
        response += f"   🛒 Recent Orders: {metrics['recent_orders_count']}\n"
        response += f"   💰 Recent Order Value: ${metrics['recent_orders_value']:,.2f}\n"
        response += f"   📄 Outstanding Invoices: {metrics['outstanding_invoices_count']}\n"
        response += f"   💳 Outstanding Amount: ${metrics['outstanding_amount']:,.2f}\n"
        response += f"   🎫 Open Support Tickets: {metrics['open_support_tickets']}\n"
        response += f"   📋 Total Support Tickets: {metrics['total_support_tickets']}\n\n"
        
        # Recent Orders
        recent_orders = data.get("recent_orders", [])
        if recent_orders:
            response += "🛒 **Recent Orders:**\n"
            for order in recent_orders:
                order_date = order.get('date_order', 'N/A')
                if order_date != 'N/A':
                    order_date = order_date[:10]  # Format date
                response += f"   • {order['name']} - ${order['amount_total']:,.2f} ({order['state']}) - {order_date}\n"
            response += "\n"
        
        # Outstanding Invoices
        outstanding = data.get("outstanding_invoices", [])
        if outstanding:
            response += "💳 **Outstanding Invoices:**\n"
            for invoice in outstanding:
                inv_date = invoice.get('invoice_date', 'N/A')
                if inv_date != 'N/A':
                    inv_date = inv_date[:10]  # Format date
                response += f"   • {invoice['name']} - ${invoice['amount_residual']:,.2f} ({invoice['payment_state']}) - {inv_date}\n"
            response += "\n"
        
        # Support Tickets
        tickets = data.get("support_tickets", [])
        if tickets:
            response += "🎫 **Recent Support Tickets:**\n"
            for ticket in tickets:
                ticket_date = ticket.get('create_date', 'N/A')
                if ticket_date != 'N/A':
                    ticket_date = ticket_date[:10]  # Format date
                stage = ticket.get('stage_id', ['', 'Unknown'])
                stage_name = stage[1] if isinstance(stage, list) and len(stage) > 1 else str(stage)
                priority = ticket.get('priority', 'Normal')
                response += f"   • {ticket['name']} - {stage_name} ({priority}) - {ticket_date}\n"
            response += "\n"
        
        response += f"🕒 **Generated:** {summary_data.get('generated_at', 'Unknown')}\n"
        
        return response
    
    def get_available_reports(self) -> List[str]:
        """Get list of available report templates
        
        Returns:
            List of available report keys
        """
        return list(self.report_templates.keys())

# This will be initialized with the odoo_client when needed
reporting_service = None