from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from typing import Dict, List, Tuple


class IntentDetector:
    def __init__(self):
        self.intents = {
            "stock_status": [
                "what is the current stock",
                "show me inventory",
                "how many units do we have",
                "current inventory levels",
                "stock status",
                "what's in stock",
                "inventory count",
                "available stock",
                "stock levels"
            ],
            "forecast_query": [
                "what's the forecast",
                "predict demand",
                "future demand",
                "forecast for next month",
                "expected sales",
                "demand prediction",
                "sales forecast",
                "how much will we sell"
            ],
            "restock_suggestion": [
                "what should I restock",
                "restock recommendations",
                "how much to order",
                "order suggestions",
                "what needs restocking",
                "reorder points",
                "restock advice",
                "order quantities"
            ],
            "stockout_risk": [
                "stockout risk",
                "will we run out",
                "stockout probability",
                "risk of stockout",
                "when will we run out",
                "stockout analysis",
                "out of stock risk",
                "getting out of stock",
                "will it get out of stock",
                "when will it run out",
                "is it getting out of stock",
                "will it stockout",
                "stockout soon",
                "run out of stock"
            ],
            "product_details": [
                "tell me about",
                "show details for",
                "product information",
                "details about",
                "information on",
                "product specs",
                "what can you tell me about"
            ],
            "comparison": [
                "compare",
                "versus",
                "vs",
                "difference between",
                "which is better",
                "compare products",
                "product comparison"
            ]
        }
        
        # Initialize TF-IDF vectorizer
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            stop_words='english',
            lowercase=True
        )
        
        # Fit vectorizer on all intent examples
        all_examples = []
        intent_labels = []
        
        for intent, examples in self.intents.items():
            for example in examples:
                all_examples.append(example)
                intent_labels.append(intent)
        
        self.intent_vectors = self.vectorizer.fit_transform(all_examples)
        self.intent_labels = intent_labels
    
    def detect_intent(self, query: str) -> Dict[str, any]:
        """
        Detect intent from user query using TF-IDF and cosine similarity.
        
        Args:
            query: User input string
            
        Returns:
            Dictionary with intent, confidence, and alternatives
        """
        # Preprocess query
        query = query.lower().strip()
        
        # Vectorize query
        query_vector = self.vectorizer.transform([query])
        
        # Calculate cosine similarity with all intent examples
        similarities = cosine_similarity(query_vector, self.intent_vectors)
        
        # Get best match
        best_idx = np.argmax(similarities[0])
        best_score = similarities[0][best_idx]
        best_intent = self.intent_labels[best_idx]
        
        # Get top 3 alternatives
        top_indices = np.argsort(similarities[0])[::-1][:3]
        alternatives = [
            {
                "intent": self.intent_labels[idx],
                "confidence": float(similarities[0][idx])
            }
            for idx in top_indices
            if idx != best_idx
        ]
        
        # Determine if confidence is high enough
        confidence_threshold = 0.3
        is_confident = best_score >= confidence_threshold
        
        return {
            "intent": best_intent if is_confident else "unknown",
            "confidence": float(best_score),
            "is_confident": is_confident,
            "alternatives": alternatives
        }
    
    def add_training_example(self, intent: str, example: str):
        """
        Add new training example for an intent.
        """
        if intent not in self.intents:
            self.intents[intent] = []
        
        self.intents[intent].append(example.lower())
        
        # Retrain vectorizer
        all_examples = []
        intent_labels = []
        
        for intent_name, examples in self.intents.items():
            for example_text in examples:
                all_examples.append(example_text)
                intent_labels.append(intent_name)
        
        self.intent_vectors = self.vectorizer.fit_transform(all_examples)
        self.intent_labels = intent_labels
