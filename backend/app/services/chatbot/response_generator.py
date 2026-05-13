from typing import Dict, List, Any
import requests
from datetime import datetime


class ResponseGenerator:
    def __init__(self, api_url: str):
        self.api_url = api_url
    
    def generate_response(self, intent: str, entities: Dict[str, List[str]], context: Dict[str, Any]) -> str:
        """
        Generate dynamic response based on intent, entities, and context.
        
        Args:
            intent: Detected user intent
            entities: Extracted entities
            context: Conversation context
            
        Returns:
            Generated response string
        """
        
        try:
            if intent == "stock_status":
                return self._generate_stock_status_response(entities, context)
            elif intent == "forecast_query":
                return self._generate_forecast_response(entities, context)
            elif intent == "restock_suggestion":
                return self._generate_restock_response(entities, context)
            elif intent == "stockout_risk":
                return self._generate_stockout_risk_response(entities, context)
            elif intent == "product_details":
                return self._generate_product_details_response(entities, context)
            elif intent == "comparison":
                return self._generate_comparison_response(entities, context)
            else:
                return self._generate_fallback_response(entities, context)
                
        except Exception as e:
            return f"I apologize, but I encountered an error while processing your request: {str(e)}"
    
    def _generate_stock_status_response(self, entities: Dict, context: Dict) -> str:
        """Generate stock status response."""
        products = entities.get("products", [])
        
        if not products and context.get("last_products"):
            products = context["last_products"]
        
        if not products:
            return "Which product would you like to check the stock status for?"
        
        # Fetch inventory data
        try:
            response = requests.get(f"{self.api_url}/inventory")
            if response.status_code == 200:
                inventory = response.json()
                
                # Filter for requested products
                product_inventory = [
                    item for item in inventory 
                    if item["product_name"].lower() in [p.lower() for p in products]
                ]
                
                if product_inventory:
                    result = "Here's the current stock status:\n\n"
                    for item in product_inventory:
                        result += f"• {item['product_name']}: {item['current_stock']} units\n"
                    return result
                else:
                    return f"I couldn't find stock information for: {', '.join(products)}"
            else:
                return "Sorry, I'm having trouble accessing inventory data right now."
        except:
            return "Sorry, I'm having trouble connecting to the inventory system."
    
    def _generate_forecast_response(self, entities: Dict, context: Dict) -> str:
        """Generate forecast response."""
        products = entities.get("products", [])
        
        if not products and context.get("last_products"):
            products = context["last_products"]
        
        if not products:
            return "Which product would you like to see the forecast for?"
        
        try:
            response = requests.get(f"{self.api_url}/forecast-next-month")
            if response.status_code == 200:
                forecasts = response.json()
                
                # Filter for requested products
                product_forecasts = [
                    item for item in forecasts 
                    if item["product_name"].lower() in [p.lower() for p in products]
                ]
                
                if product_forecasts:
                    result = "Here are the demand forecasts:\n\n"
                    for item in product_forecasts:
                        result += f"• {item['product_name']}: {item['forecast_units']} units forecasted for {item['forecast_month']}\n"
                    return result
                else:
                    return f"I couldn't find forecast data for: {', '.join(products)}"
            else:
                return "Sorry, I'm having trouble accessing forecast data right now."
        except:
            return "Sorry, I'm having trouble connecting to the forecasting system."
    
    def _generate_restock_response(self, entities: Dict, context: Dict) -> str:
        """Generate restock suggestion response."""
        products = entities.get("products", [])
        
        if not products and context.get("last_products"):
            products = context["last_products"]
        
        if not products:
            return "Which products would you like restock suggestions for?"
        
        try:
            response = requests.get(f"{self.api_url}/restock-recommendations")
            if response.status_code == 200:
                restock_data = response.json()
                
                # Filter for requested products
                product_restock = [
                    item for item in restock_data 
                    if item["product_name"].lower() in [p.lower() for p in products]
                ]
                
                if product_restock:
                    result = "Here are the restock recommendations:\n\n"
                    total_restock = 0
                    for item in product_restock:
                        if item["recommended_order_qty"] > 0:
                            result += f"• {item['product_name']}: Order {item['recommended_order_qty']} units (Current: {item['current_stock']}, Reorder Point: {item['reorder_point']})\n"
                            total_restock += item["recommended_order_qty"]
                        else:
                            result += f"• {item['product_name']}: No restock needed (Current: {item['current_stock']})\n"
                    
                    if total_restock > 0:
                        result += f"\nTotal recommended order: {total_restock} units"
                    
                    return result
                else:
                    return f"I couldn't find restock data for: {', '.join(products)}"
            else:
                return "Sorry, I'm having trouble accessing restock recommendations right now."
        except:
            return "Sorry, I'm having trouble connecting to the restock system."
    
    def _generate_stockout_risk_response(self, entities: Dict, context: Dict) -> str:
        """Generate stockout risk response."""
        products = entities.get("products", [])
        time_expressions = entities.get("time_expressions", [])
        numbers = entities.get("numbers", [])
        
        if not products and context.get("last_products"):
            products = context["last_products"]
        
        if not products:
            return "Which products would you like to check for stockout risk?"
        
        try:
            # Get stockout risk data
            response = requests.get(f"{self.api_url}/stockout-risk")
            if response.status_code == 200:
                stockout_data = response.json()
                
                # Filter for requested products
                product_risks = [
                    item for item in stockout_data 
                    if item["product_name"].lower() in [p.lower() for p in products]
                ]
                
                if product_risks:
                    result = "Here's the stockout risk analysis:\n\n"
                    for item in product_risks:
                        current_stock = item["current_stock"]
                        predicted_demand = item["predicted_next_n_days"]
                        
                        # Determine risk level
                        if predicted_demand > current_stock:
                            risk_level = "HIGH"
                            risk_desc = f"⚠️  **HIGH RISK** - Will run out of stock!"
                            days_until_stockout = max(1, current_stock // max(1, predicted_demand // current_stock))
                            timing = f"Expected to run out in ~{days_until_stockout} days"
                        else:
                            risk_level = "LOW"
                            risk_desc = f"✅ **LOW RISK** - Stock levels are adequate"
                            timing = f"Current stock should last through the forecast period"
                        
                        result += f"📦 **{item['product_name'].title()}**\n"
                        result += f"   Current Stock: {current_stock} units\n"
                        result += f"   Predicted Demand: {predicted_demand} units\n"
                        result += f"   Risk Level: {risk_desc}\n"
                        result += f"   Analysis: {timing}\n\n"
                    
                    # Add time-specific analysis if provided
                    if time_expressions or numbers:
                        result += "**Time-based Analysis:**\n"
                        if numbers:
                            for num in numbers:
                                result += f"• Forecast period: {num['value']} days\n"
                        if time_expressions:
                            result += f"• Time context: {', '.join(time_expressions)}\n"
                    
                    return result
                else:
                    return f"I couldn't find stockout risk data for: {', '.join(products)}"
            else:
                return "Sorry, I'm having trouble accessing stockout risk data right now."
        except Exception as e:
            return f"Sorry, I'm having trouble connecting to the stockout risk system: {str(e)}"
    
    def _generate_product_details_response(self, entities: Dict, context: Dict) -> str:
        """Generate comprehensive product details response."""
        products = entities.get("products", [])
        
        if not products and context.get("last_products"):
            products = context["last_products"]
        
        if not products:
            return "Which product would you like detailed information about?"
        
        try:
            # Get multiple data sources
            inventory_response = requests.get(f"{self.api_url}/inventory")
            safety_response = requests.get(f"{self.api_url}/safety-stock")
            restock_response = requests.get(f"{self.api_url}/restock-recommendations")
            
            if all([r.status_code == 200 for r in [inventory_response, safety_response, restock_response]]):
                inventory = inventory_response.json()
                safety_stock = safety_response.json()
                restock = restock_response.json()
                
                result = "Here are the comprehensive product details:\n\n"
                
                for product in products:
                    # Find product data
                    inv_item = next((i for i in inventory if i["product_name"].lower() == product.lower()), None)
                    safety_item = next((s for s in safety_stock if s["product_name"].lower() == product.lower()), None)
                    restock_item = next((r for r in restock if r["product_name"].lower() == product.lower()), None)
                    
                    if inv_item:
                        result += f"📦 {product.title()}\n"
                        result += f"  Current Stock: {inv_item['current_stock']} units\n"
                        
                        if safety_item:
                            result += f"  Reorder Point: {safety_item['reorder_point']} units\n"
                            result += f"  Safety Stock: {safety_item['safety_stock']} units\n"
                            result += f"  Avg Daily Demand: {safety_item['avg_daily_demand']:.2f} units\n"
                            result += f"  Lead Time: {safety_item['lead_time_days']} days\n"
                        
                        if restock_item:
                            if restock_item["recommended_order_qty"] > 0:
                                result += f"  ⚠️  RECOMMENDED RESTOCK: {restock_item['recommended_order_qty']} units\n"
                            else:
                                result += f"  ✅ No restock needed\n"
                        
                        result += "\n"
                    else:
                        result += f"❌ {product.title()}: Product not found in inventory\n\n"
                
                return result
            else:
                return "Sorry, I'm having trouble accessing product data right now."
        except:
            return "Sorry, I'm having trouble connecting to the product database."
    
    def _generate_comparison_response(self, entities: Dict, context: Dict) -> str:
        """Generate product comparison response."""
        products = entities.get("products", [])
        
        if len(products) < 2:
            return "Please specify at least two products to compare. For example: 'compare rice and wheat'"
        
        try:
            inventory_response = requests.get(f"{self.api_url}/inventory")
            safety_response = requests.get(f"{self.api_url}/safety-stock")
            
            if all([r.status_code == 200 for r in [inventory_response, safety_response]]):
                inventory = inventory_response.json()
                safety_stock = safety_response.json()
                
                result = f"📊 Comparison of {len(products)} products:\n\n"
                
                for product in products:
                    inv_item = next((i for i in inventory if i["product_name"].lower() == product.lower()), None)
                    safety_item = next((s for s in safety_stock if s["product_name"].lower() == product.lower()), None)
                    
                    if inv_item and safety_item:
                        result += f"🏷️  {product.title()}\n"
                        result += f"   Stock Level: {inv_item['current_stock']} units\n"
                        result += f"   Safety Stock: {safety_item['safety_stock']} units\n"
                        result += f"   Reorder Point: {safety_item['reorder_point']} units\n"
                        result += f"   Stock Status: {'⚠️ Below Reorder Point' if inv_item['current_stock'] < safety_item['reorder_point'] else '✅ OK'}\n\n"
                    else:
                        result += f"❌ {product.title()}: Data not available\n\n"
                
                return result
            else:
                return "Sorry, I'm having trouble accessing comparison data right now."
        except:
            return "Sorry, I'm having trouble connecting to the comparison system."
    
    def _generate_fallback_response(self, entities: Dict, context: Dict) -> str:
        """Generate fallback response for unknown intents."""
        return """I'm not sure I understand. I can help you with:

📦 Stock Status - "What's the current stock for rice?"
📈 Forecast - "Show me the forecast for wheat"
🔄 Restock - "What should I restock for rice?"
⚠️  Stockout Risk - "Is there a stockout risk for wheat?"
📋 Product Details - "Tell me about rice"
📊 Comparison - "Compare rice and wheat"

Please try rephrasing your question or choose from the options above."""
