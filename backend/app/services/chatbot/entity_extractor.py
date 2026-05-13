import re
from typing import List, Dict, Tuple
from fuzzywuzzy import fuzz, process


class EntityExtractor:
    def __init__(self, available_products: List[str] = None):
        self.available_products = available_products or []
        
        # Product name patterns
        self.product_patterns = [
            r'(?:product|item|stock|inventory)\s+(?:for|of)?\s*([a-zA-Z\s]+)',
            r'(?:show|tell|get|what|how many)\s+(?:is|are)?\s*([a-zA-Z\s]+?)(?:\s+(?:stock|inventory|forecast|details?))?',
            r'(?:details?|information|about|for)\s*([a-zA-Z\s]+)',
            r'^([a-zA-Z\s]+?)(?:\s+(?:stock|inventory|forecast|details?))?',
            r'(?:what\s+is\s+the\s+stock\s+(?:of|for)?\s*([a-zA-Z\s]+))',
        ]
        
        # Compile patterns
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.product_patterns]
    
    def extract_entities(self, query: str) -> Dict[str, List[str]]:
        """
        Extract entities from user query.
        
        Args:
            query: User input string
            
        Returns:
            Dictionary with extracted entities
        """
        entities = {
            "products": [],
            "numbers": [],
            "time_expressions": []
        }
        
        # Extract product names
        products = self._extract_products(query)
        entities["products"] = products
        
        # Extract numbers (quantities, days)
        numbers = self._extract_numbers(query)
        entities["numbers"] = numbers
        
        # Extract time expressions
        time_expressions = self._extract_time_expressions(query)
        entities["time_expressions"] = time_expressions
        
        return entities
    
    def _extract_products(self, query: str) -> List[str]:
        """
        Extract product names using patterns and fuzzy matching.
        """
        products = []
        query_lower = query.lower()
        
        # Skip extraction if query contains pronouns (let context manager handle it)
        pronouns = ['it', 'that', 'this', 'the product', 'the item']
        has_pronoun = any(pronoun in query_lower for pronoun in pronouns)
        
        if not has_pronoun:
            # Try pattern-based extraction first
            for pattern in self.compiled_patterns:
                matches = pattern.findall(query)
                for match in matches:
                    product_name = match.strip()
                    if product_name and len(product_name) > 1:
                        products.append(product_name)
            
            # If no pattern matches, try fuzzy matching with available products
            if not products and self.available_products:
                # Split query into potential words/phrases
                words = re.findall(r'\b[a-zA-Z]+\b', query)
                
                # Try combinations of words
                for i in range(len(words)):
                    for j in range(i + 1, min(i + 4, len(words) + 1)):  # Up to 3-word phrases
                        phrase = ' '.join(words[i:j])
                        
                        # Fuzzy match with available products
                        match = process.extractOne(
                            phrase.lower(),
                            [p.lower() for p in self.available_products],
                            scorer=fuzz.partial_ratio,
                            score_cutoff=60
                        )
                        
                        if match:
                            # Get the original case product name
                            original_product = self.available_products[
                                [p.lower() for p in self.available_products].index(match[0])
                            ]
                            if original_product not in products:
                                products.append(original_product)
        
        return products
    
    def _extract_numbers(self, query: str) -> List[Dict[str, int]]:
        """
        Extract numbers and their context.
        """
        numbers = []
        
        # Pattern to find numbers with optional context
        number_pattern = r'(\d+)\s*(?:days?|units?|items?|products?|pieces?)?'
        matches = re.findall(number_pattern, query, re.IGNORECASE)
        
        for match in matches:
            numbers.append({
                "value": int(match),
                "context": "quantity"  # Could be enhanced with more context extraction
            })
        
        return numbers
    
    def _extract_time_expressions(self, query: str) -> List[str]:
        """
        Extract time-related expressions.
        """
        time_patterns = [
            r'\b(?:next|upcoming|following)\s+(\d+)\s+(?:week|month|day)s?\b',
            r'\b(?:this|current)\s+(?:week|month|day)s?\b',
            r'\b(?:last|previous|past)\s+(?:week|month|day)s?\b',
            r'\b(?:daily|weekly|monthly)\b',
            r'\b(?:in\s+)?next\s+(\d+)\s+(?:week|month|day)s?\b'
        ]
        
        time_expressions = []
        for pattern in time_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            time_expressions.extend(matches)
        
        return list(set(time_expressions))  # Remove duplicates
    
    def update_available_products(self, products: List[str]):
        """
        Update the list of available products.
        """
        self.available_products = products
    
    def resolve_pronouns(self, query: str, last_products: List[str]) -> List[str]:
        """
        Resolve pronouns (it, that, this) to actual product names.
        """
        resolved_products = []
        query_lower = query.lower()
        
        # Check for pronouns
        pronouns = ['it', 'that', 'this', 'the product', 'the item']
        
        for pronoun in pronouns:
            if pronoun in query_lower and last_products:
                # Use the most recently mentioned product
                resolved_products.extend(last_products[-1:])  # Last mentioned product
                break
        
        # Also extract any new product names
        new_products = self._extract_products(query)
        resolved_products.extend(new_products)
        
        return list(set(resolved_products))  # Remove duplicates
