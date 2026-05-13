from typing import Dict, Any
import requests
from .intent_detector import IntentDetector
from .entity_extractor import EntityExtractor
from .response_generator import ResponseGenerator
from .context_manager import ContextManager


class ChatBot:
    def __init__(self, api_url: str):
        self.api_url = api_url
        self.intent_detector = IntentDetector()
        self.entity_extractor = EntityExtractor()
        self.response_generator = ResponseGenerator(api_url)
        self.context_manager = ContextManager()
        
        # Initialize with available products
        self._update_product_list()
    
    def _update_product_list(self):
        """Update entity extractor with available products."""
        try:
            response = requests.get(f"{self.api_url}/inventory")
            if response.status_code == 200:
                inventory = response.json()
                products = [item["product_name"] for item in inventory]
                self.entity_extractor.update_available_products(products)
        except:
            # If API is not available, continue with empty product list
            pass
    
    def process_query(self, user_query: str) -> Dict[str, Any]:
        """
        Process user query and generate response.
        
        Args:
            user_query: User input string
            
        Returns:
            Dictionary with response and metadata
        """
        try:
            # Step 1: Detect intent
            intent_result = self.intent_detector.detect_intent(user_query)
            intent = intent_result["intent"]
            confidence = intent_result["confidence"]
            
            # Step 2: Extract entities
            entities = self.entity_extractor.extract_entities(user_query)
            
            # Step 3: Handle pronouns and context
            context = self.context_manager.get_context()
            
            # Check if this is a follow-up question
            if self.context_manager.is_follow_up_question(user_query):
                # Resolve pronouns to actual product names
                resolved_products = self.entity_extractor.resolve_pronouns(
                    user_query, 
                    context.get("last_products", [])
                )
                if resolved_products:
                    entities["products"] = resolved_products
            
            # Step 4: Generate response
            response = self.response_generator.generate_response(intent, entities, context)
            
            # Step 5: Update context
            self.context_manager.update_context(user_query, intent, entities, response)
            
            # Step 6: Re-train intent detector if confidence is low
            if not intent_result["is_confident"] and intent != "unknown":
                # This could be enhanced with user feedback in future
                pass
            
            return {
                "response": response,
                "intent": intent,
                "confidence": confidence,
                "entities": entities,
                "context": context
            }
            
        except Exception as e:
            error_response = f"I apologize, but I encountered an error: {str(e)}"
            
            # Update context with error
            self.context_manager.update_context(
                user_query, 
                "error", 
                {"error": str(e)}, 
                error_response
            )
            
            return {
                "response": error_response,
                "intent": "error",
                "confidence": 0.0,
                "entities": {},
                "context": self.context_manager.get_context()
            }
    
    def add_training_example(self, intent: str, example: str):
        """
        Add training example to improve intent detection.
        
        Args:
            intent: Correct intent for the example
            example: User query example
        """
        self.intent_detector.add_training_example(intent, example)
    
    def get_conversation_summary(self) -> str:
        """
        Get summary of current conversation.
        
        Returns:
            Conversation summary string
        """
        return self.context_manager.get_conversation_summary()
    
    def clear_conversation(self):
        """
        Clear conversation history and start fresh.
        """
        self.context_manager.clear_context()
        return "Conversation cleared. How can I help you today?"
    
    def get_capabilities(self) -> str:
        """
        Return list of chatbot capabilities.
        
        Returns:
            Capabilities description
        """
        return """I can help you with retail supply chain management:

📦 **Stock Status** - Check current inventory levels
   "What's the stock for rice?" or "Show me inventory"

📈 **Forecast** - Get demand predictions
   "What's the forecast for wheat?" or "Predict demand for rice"

🔄 **Restock** - Get ordering recommendations
   "What should I restock?" or "Restock suggestions for rice"

⚠️ **Stockout Risk** - Check for potential stockouts
   "Is there a stockout risk for wheat?" or "Will we run out of rice?"

📋 **Product Details** - Get comprehensive product information
   "Tell me about rice" or "Details for wheat"

📊 **Comparison** - Compare multiple products
   "Compare rice and wheat" or "Rice vs wheat"

I understand follow-up questions like "What about its stock?" or "How about wheat too?"""
    
    def handle_action_intent(self, intent: str, entities: Dict[str, Any]) -> str:
        """
        Handle action-oriented intents that trigger backend operations.
        
        Args:
            intent: Detected action intent
            entities: Extracted entities
            
        Returns:
            Result message
        """
        try:
            if intent == "restock_suggestion":
                # Trigger bulk restock for specific products
                products = entities.get("products", [])
                if products:
                    # Prepare bulk restock request
                    bulk_items = []
                    for product in products:
                        # Get recommended quantity
                        restock_response = requests.get(f"{self.api_url}/restock-recommendations")
                        if restock_response.status_code == 200:
                            restock_data = restock_response.json()
                            for item in restock_data:
                                if item["product_name"].lower() == product.lower() and item["recommended_order_qty"] > 0:
                                    bulk_items.append({
                                        "product_name": product,
                                        "quantity_added": item["recommended_order_qty"]
                                    })
                    
                    if bulk_items:
                        # Execute bulk restock
                        response = requests.post(
                            f"{self.api_url}/bulk-restock",
                            json={"items": bulk_items}
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            return f"✅ Successfully restocked {len(bulk_items)} products. {result['message']}"
                        else:
                            return f"❌ Failed to restock: {response.text}"
                    else:
                        return f"No restock needed for: {', '.join(products)}"
                else:
                    return "Please specify which products you'd like to restock."
            
            return "Action not implemented for this intent."
            
        except Exception as e:
            return f"Error executing action: {str(e)}"
