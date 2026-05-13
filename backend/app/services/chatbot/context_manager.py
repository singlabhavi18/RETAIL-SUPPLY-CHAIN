from typing import Dict, List, Any
from datetime import datetime


class ContextManager:
    def __init__(self):
        self.conversation_history = []
        self.last_products = []
        self.last_intent = None
        self.session_start = datetime.now()
        self.context_window = 5  # Remember last 5 exchanges
    
    def update_context(self, user_query: str, intent: str, entities: Dict[str, List[str]], response: str):
        """
        Update conversation context after each interaction.
        
        Args:
            user_query: User's input
            intent: Detected intent
            entities: Extracted entities
            response: Bot's response
        """
        # Create conversation turn
        turn = {
            "timestamp": datetime.now(),
            "user_query": user_query,
            "intent": intent,
            "entities": entities,
            "response": response
        }
        
        # Add to history
        self.conversation_history.append(turn)
        
        # Update last products mentioned
        products = entities.get("products", [])
        if products:
            self.last_products.extend(products)
            # Keep only unique products from last 10 mentions
            unique_products = []
            seen = set()
            for product in reversed(self.last_products):
                if product.lower() not in seen:
                    seen.add(product.lower())
                    unique_products.append(product)
                if len(unique_products) >= 10:
                    break
            self.last_products = list(reversed(unique_products))
        
        # Update last intent
        self.last_intent = intent
        
        # Trim conversation history to context window
        if len(self.conversation_history) > self.context_window * 2:  # User + bot turns
            self.conversation_history = self.conversation_history[-self.context_window * 2:]
    
    def get_context(self) -> Dict[str, Any]:
        """
        Get current conversation context.
        
        Returns:
            Dictionary with context information
        """
        return {
            "last_products": self.last_products,
            "last_intent": self.last_intent,
            "conversation_history": self.conversation_history[-self.context_window:],
            "session_duration": (datetime.now() - self.session_start).total_seconds() / 60  # minutes
        }
    
    def get_recent_intents(self, count: int = 3) -> List[str]:
        """
        Get recent intents for pattern detection.
        
        Args:
            count: Number of recent intents to return
            
        Returns:
            List of recent intents
        """
        recent_turns = [turn for turn in self.conversation_history if turn["intent"] != "unknown"]
        return [turn["intent"] for turn in recent_turns[-count:]]
    
    def is_follow_up_question(self, current_query: str) -> bool:
        """
        Determine if current query is a follow-up to previous conversation.
        
        Args:
            current_query: Current user input
            
        Returns:
            True if this appears to be a follow-up
        """
        query_lower = current_query.lower().strip()
        
        # Follow-up indicators
        follow_up_indicators = [
            "what about", "how about", "and", "also", "too", "as well",
            "it", "that", "this", "the same", "similar",
            "what if", "can you also", "tell me more"
        ]
        
        # Check if query contains follow-up indicators
        is_follow_up = any(indicator in query_lower for indicator in follow_up_indicators)
        
        # Also check if query is very short (likely pronoun reference)
        if len(query_lower.split()) <= 3 and self.last_products:
            is_follow_up = True
        
        return is_follow_up
    
    def get_last_mentioned_product(self) -> str:
        """
        Get the most recently mentioned product.
        
        Returns:
            Product name or None if no products mentioned
        """
        return self.last_products[-1] if self.last_products else None
    
    def clear_context(self):
        """
        Clear conversation context (start fresh session).
        """
        self.conversation_history = []
        self.last_products = []
        self.last_intent = None
        self.session_start = datetime.now()
    
    def get_conversation_summary(self) -> str:
        """
        Generate a brief summary of the conversation.
        
        Returns:
            Summary string
        """
        if not self.conversation_history:
            return "No conversation history."
        
        summary_parts = []
        products_mentioned = set()
        
        for turn in self.conversation_history[-3:]:  # Last 3 turns
            if turn["intent"] != "unknown":
                products_mentioned.update(turn["entities"].get("products", []))
                summary_parts.append(f"Asked about {turn['intent']}")
        
        if products_mentioned:
            summary_parts.append(f"Products discussed: {', '.join(list(products_mentioned))}")
        
        return " | ".join(summary_parts) if summary_parts else "Recent conversation unclear."
