# src/memory/astra_vector_store.py
"""
AstraDB Vector Memory Store with VoyageAI Embeddings - FIXED VERSION
Uses correct DataAPIClient approach as per AstraDB documentation
"""
import os
import json
import logging
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests
import voyageai

# Configure logger
logger = logging.getLogger("trading_agent.astra_vector_store")

# Load environment variables
load_dotenv()

# Configuration
ASTRA_DB_APPLICATION_TOKEN = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
ASTRA_DB_API_ENDPOINT = os.getenv("ASTRA_DB_API_ENDPOINT")
VOYAGEAI_API_KEY = os.getenv("VOYAGEAI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Fallback

# Collection configuration
COLLECTION_NAME = "pure_ai_trading_memory"
EMBEDDING_DIMENSION = 1024  # Voyage AI embedding dimension

# Global variables
_initialized = False
_initialization_failed = False
_db_client = None
_collection = None

class AstraDBVectorStore:
    """AstraDB Vector Store with VoyageAI embeddings - Fixed Implementation"""
    
    def __init__(self):
        self.token = ASTRA_DB_APPLICATION_TOKEN
        self.endpoint = ASTRA_DB_API_ENDPOINT
        self.voyageai_key = VOYAGEAI_API_KEY
        self.openai_key = OPENAI_API_KEY
        self.collection_name = COLLECTION_NAME
        self.client = None
        self.db = None
        self.collection = None
        
        if self.token and self.endpoint:
            logger.info("AstraDB client initialized with correct credentials")
        else:
            logger.warning("AstraDB client initialized without proper credentials")
    
    def _get_voyageai_embedding(self, text: str) -> List[float]:
        """Get high-quality embedding from VoyageAI - FIXED VERSION"""
        if not self.voyageai_key:
            logger.warning("No VoyageAI API key, falling back to OpenAI")
            return self._get_openai_embedding(text)
        
        try:
            vo = voyageai.Client(api_key=self.voyageai_key)
            
            # FIXED: Correct API call according to documentation
            result = vo.embed(
                texts=[text],  # Must be a list
                model="voyage-3.5",
                input_type="document"
            )
            
            # FIXED: Correct way to access embeddings
            if result and result.embeddings:
                embedding = result.embeddings[0]  # Get first (and only) embedding
                logger.debug(f"Generated VoyageAI embedding of dimension {len(embedding)}")
                return embedding
            else:
                logger.error(f"VoyageAI API returned no embeddings for text: {text[:100]}...")
                return self._get_openai_embedding(text)

        except Exception as e:
            logger.error(f"Error getting VoyageAI embedding: {e}")
            return self._get_openai_embedding(text)
    
    def _get_openai_embedding(self, text: str) -> List[float]:
        """Fallback to OpenAI embeddings if VoyageAI fails"""
        if not self.openai_key:
            logger.warning("No OpenAI API key, using simple hash embedding")
            return self._get_hash_embedding(text)
        
        try:
            import openai
            client = openai.OpenAI(api_key=self.openai_key)
            response = client.embeddings.create(
                input=text,
                model="text-embedding-ada-002"
            )
            embedding = response.data[0].embedding
            
            # Pad or truncate to match VoyageAI dimension
            if len(embedding) > EMBEDDING_DIMENSION:
                embedding = embedding[:EMBEDDING_DIMENSION]
            elif len(embedding) < EMBEDDING_DIMENSION:
                embedding.extend([0.0] * (EMBEDDING_DIMENSION - len(embedding)))
            
            logger.debug(f"Generated OpenAI embedding (padded to {EMBEDDING_DIMENSION})")
            return embedding
            
        except Exception as e:
            logger.error(f"Error getting OpenAI embedding: {e}")
            return self._get_hash_embedding(text)
    
    def _get_hash_embedding(self, text: str) -> List[float]:
        """Simple hash-based embedding as last resort"""
        import hashlib
        hash_obj = hashlib.sha256(text.encode())
        hash_int = int(hash_obj.hexdigest(), 16)
        
        embedding = []
        for i in range(EMBEDDING_DIMENSION):
            embedding.append(((hash_int >> (i % 256)) & 1) * 2.0 - 1.0)
        
        logger.debug(f"Generated hash-based embedding of dimension {EMBEDDING_DIMENSION}")
        return embedding
    
    def initialize_collection(self) -> bool:
        """Initialize AstraDB connection using the CORRECT DataAPIClient method"""
        global _initialized, _initialization_failed, _db_client, _collection
        
        if _initialized and _collection is not None:
            self.collection = _collection
            return True
        
        if _initialization_failed:
            return False
        
        if not self.token or not self.endpoint:
            logger.error("Missing AstraDB credentials - ASTRA_DB_APPLICATION_TOKEN or ASTRA_DB_API_ENDPOINT not set")
            _initialization_failed = True
            return False
        
        try:
            # Import AstraDB client
            try:
                from astrapy import DataAPIClient
                from astrapy.info import CollectionDefinition
                from astrapy.constants import VectorMetric
            except ImportError:
                logger.error("astrapy library not installed. Run: pip install astrapy")
                _initialization_failed = True
                return False
            
            # FIXED: Initialize the client using the correct method
            logger.info("Initializing AstraDB DataAPIClient...")
            client = DataAPIClient(self.token)
            
            # FIXED: Get database by API endpoint using the correct method
            logger.info(f"Connecting to AstraDB at: {self.endpoint}")
            db = client.get_database(self.endpoint)
            
            # Test connection by listing collections
            try:
                existing_collections = db.list_collection_names()
                logger.info(f"Connected to AstraDB successfully. Existing collections: {existing_collections}")
            except Exception as e:
                logger.error(f"Failed to list collections: {e}")
                _initialization_failed = True
                return False
            
            # Check if our collection exists
            if self.collection_name not in existing_collections:
                logger.info(f"Creating collection '{self.collection_name}' with {EMBEDDING_DIMENSION}D vectors")
                
                # FIXED: Create collection with vector configuration using CollectionDefinition
                collection_definition = (
                    CollectionDefinition.builder()
                    .set_vector_dimension(EMBEDDING_DIMENSION)
                    .set_vector_metric(VectorMetric.COSINE)
                    .build()
                )
                
                collection = db.create_collection(
                    self.collection_name,
                    definition=collection_definition
                )
                
                logger.info(f"Created collection '{self.collection_name}' successfully")
            else:
                # Get existing collection
                collection = db.get_collection(self.collection_name)
                logger.info(f"Connected to existing collection '{self.collection_name}'")
            
            # Store references globally
            _db_client = client
            _collection = collection
            self.client = client
            self.db = db
            self.collection = collection
            
            _initialized = True
            logger.info("AstraDB initialization completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing AstraDB: {e}")
            _initialization_failed = True
            return False
    
    def add_trading_experience(self, token_address: str, trading_data: Dict[str, Any]) -> str:
        """Add trading experience to vector memory for AI learning"""
        if not self.initialize_collection():
            logger.warning("AstraDB not available, skipping experience storage")
            return ""
        
        try:
            # Generate document ID
            doc_id = str(uuid.uuid4())
            timestamp = datetime.now().isoformat()
            
            # Create rich document text for embedding (trading-focused)
            token_symbol = trading_data.get("token_symbol", "unknown")
            trade_type = trading_data.get("trade_type", "analysis")
            profit_pct = trading_data.get("profit_percentage", 0)
            ai_reasoning = trading_data.get("ai_reasoning", "")
            market_conditions = trading_data.get("market_conditions", {})
            
            # Create comprehensive text for semantic search
            document_text = f"""
            Token Analysis: {token_symbol} ({token_address})
            Trade Type: {trade_type}
            Performance: {profit_pct:+.1f}% profit
            Market Conditions: {json.dumps(market_conditions)}
            AI Reasoning: {ai_reasoning}
            
            Key Metrics:
            Safety Score: {trading_data.get('safety_score', 0):.1f}
            Social Activity: {trading_data.get('social_activity', 0):.1f}
            Viral Score: {trading_data.get('viral_score', 0):.1f}
            Market Health: {trading_data.get('market_health_score', 0):.1f}
            
            Trade Details:
            Entry Price: ${trading_data.get('entry_price_usd', 0):.6f}
            Exit Price: ${trading_data.get('exit_price_usd', 0):.6f}
            Hold Time: {trading_data.get('hold_time_hours', 0):.1f} hours
            Position Size: {trading_data.get('position_size_sol', 0):.4f} SOL
            
            Lessons Learned: {trading_data.get('lessons_learned', '')}
            Strategy Used: {trading_data.get('strategy', 'unknown')}
            Success Factors: {json.dumps(trading_data.get('success_factors', []))}
            Risk Factors: {json.dumps(trading_data.get('risk_factors', []))}
            """
            
            # Get high-quality embedding
            embedding = self._get_voyageai_embedding(document_text)
            
            # Prepare document with rich metadata for filtering
            document = {
                "_id": doc_id,
                "document_type": "trading_experience",
                "token_address": token_address,
                "token_symbol": token_symbol,
                "timestamp": timestamp,
                
                # Trading metadata
                "trade_type": trade_type,
                "profit_percentage": profit_pct,
                "was_profitable": profit_pct > 0,
                "position_size_sol": trading_data.get("position_size_sol", 0),
                "hold_time_hours": trading_data.get("hold_time_hours", 0),
                "strategy": trading_data.get("strategy", "unknown"),
                
                # Performance metrics
                "safety_score": trading_data.get("safety_score", 0),
                "social_activity": trading_data.get("social_activity", 0),
                "viral_score": trading_data.get("viral_score", 0),
                "market_health_score": trading_data.get("market_health_score", 0),
                "overall_score": trading_data.get("overall_score", 0),
                
                # Market context
                "market_sentiment": market_conditions.get("sentiment", "neutral"),
                "market_volatility": market_conditions.get("volatility", "medium"),
                
                # Content
                "document_text": document_text,
                "ai_reasoning": ai_reasoning,
                "complete_trading_data": trading_data,
                
                # Vector embedding
                "$vector": embedding
            }
            
            # Insert document using correct AstraDB method
            result = self.collection.insert_one(document)
            
            if result and result.inserted_id:
                logger.info(f"Added trading experience for {token_symbol} to vector memory: {doc_id}")
                return doc_id
            else:
                logger.error(f"Failed to insert trading experience: {result}")
                return ""
                
        except Exception as e:
            logger.error(f"Error adding trading experience to vector memory: {e}")
            return ""
    
    def search_similar_experiences(self, query: str, limit: int = 5, filter_criteria: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Search for similar trading experiences using semantic similarity"""
        if not self.initialize_collection():
            logger.warning("AstraDB not available, returning empty results")
            return []
        
        try:
            # Get query embedding
            query_embedding = self._get_voyageai_embedding(query)
            
            # Prepare search with vector similarity
            search_kwargs = {
                "sort": {"$vector": query_embedding},
                "limit": limit,
                "include_similarity": True
            }
            
            # Add filter if provided
            if filter_criteria:
                search_kwargs["filter"] = filter_criteria
            
            # Execute search using correct AstraDB method
            cursor = self.collection.find(**search_kwargs)
            
            processed_results = []
            for doc in cursor:
                processed_results.append({
                    "id": doc.get("_id"),
                    "similarity": doc.get("$similarity", 0.0),
                    "metadata": {
                        "token_address": doc.get("token_address"),
                        "token_symbol": doc.get("token_symbol"),
                        "trade_type": doc.get("trade_type"),
                        "profit_percentage": doc.get("profit_percentage"),
                        "was_profitable": doc.get("was_profitable"),
                        "strategy": doc.get("strategy"),
                        "timestamp": doc.get("timestamp"),
                        "hold_time_hours": doc.get("hold_time_hours"),
                        "overall_score": doc.get("overall_score"),
                        "market_sentiment": doc.get("market_sentiment")
                    },
                    "ai_reasoning": doc.get("ai_reasoning", ""),
                    "trading_data": doc.get("complete_trading_data", {}),
                    "document": doc.get("document_text", "")
                })
            
            logger.info(f"Vector search for '{query}' returned {len(processed_results)} similar experiences")
            return processed_results
            
        except Exception as e:
            logger.error(f"Error searching vector memory: {e}")
            return []
    
    def find_similar_tokens(self, token_data: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
        """Find similar tokens based on characteristics"""
        try:
            # Create search query based on token characteristics
            query_parts = []
            
            if token_data.get("symbol"):
                query_parts.append(f"Token similar to {token_data['symbol']}")
            
            if token_data.get("safety_score", 0) > 0:
                query_parts.append(f"Safety score around {token_data['safety_score']:.0f}")
            
            if token_data.get("social_activity", 0) > 0:
                query_parts.append(f"Social activity {token_data['social_activity']:.0f}")
            
            if token_data.get("market_cap", 0) > 0:
                query_parts.append(f"Market cap ${token_data['market_cap']:,.0f}")
            
            if token_data.get("liquidity_usd", 0) > 0:
                query_parts.append(f"Liquidity ${token_data['liquidity_usd']:,.0f}")
            
            query = ". ".join(query_parts)
            
            # Search for similar experiences
            results = self.search_similar_experiences(query, limit)
            
            # Extract token data from results
            similar_tokens = []
            for result in results:
                trading_data = result.get("trading_data", {})
                if trading_data:
                    similar_tokens.append({
                        "token_symbol": result["metadata"]["token_symbol"],
                        "token_address": result["metadata"]["token_address"],
                        "similarity_score": result["similarity"],
                        "profit_achieved": result["metadata"]["profit_percentage"],
                        "strategy_used": result["metadata"]["strategy"],
                        "ai_reasoning": result["ai_reasoning"],
                        "characteristics": {
                            "safety_score": trading_data.get("safety_score", 0),
                            "social_activity": trading_data.get("social_activity", 0),
                            "viral_score": trading_data.get("viral_score", 0),
                            "market_health": trading_data.get("market_health_score", 0)
                        }
                    })
            
            return similar_tokens
            
        except Exception as e:
            logger.error(f"Error finding similar tokens: {e}")
            return []
    
    def get_trading_patterns(self, pattern_type: str = "profitable") -> List[Dict[str, Any]]:
        """Get trading patterns for AI learning"""
        try:
            filter_criteria = {}
            
            if pattern_type == "profitable":
                filter_criteria["was_profitable"] = True
            elif pattern_type == "losing":
                filter_criteria["was_profitable"] = False
            elif pattern_type == "high_profit":
                filter_criteria = {"profit_percentage": {"$gte": 20}}
            elif pattern_type == "quick_trades":
                filter_criteria = {"hold_time_hours": {"$lte": 2}}
            
            # Search for patterns
            query = f"Trading patterns for {pattern_type} trades with market analysis"
            results = self.search_similar_experiences(query, limit=20, filter_criteria=filter_criteria)
            
            return results
            
        except Exception as e:
            logger.error(f"Error getting trading patterns: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        if not self.initialize_collection():
            return {
                "total_records": 0,
                "error": "AstraDB not available"
            }
        
        try:
            # Count documents using correct AstraDB method
            count = self.collection.count_documents({})
            
            # Get some sample statistics
            stats = {
                "total_records": count,
                "collection_name": self.collection_name,
                "endpoint": self.endpoint,
                "embedding_dimension": EMBEDDING_DIMENSION,
                "embedding_provider": "VoyageAI" if self.voyageai_key else ("OpenAI" if self.openai_key else "Hash"),
                "timestamp": datetime.now().isoformat(),
                "status": "healthy"
            }
            
            # Get profitable vs losing trades
            if count > 0:
                try:
                    profitable_count = self.collection.count_documents({"was_profitable": True})
                    stats["profitable_trades"] = profitable_count
                    stats["losing_trades"] = count - profitable_count
                    stats["win_rate"] = profitable_count / count if count > 0 else 0
                except:
                    stats["win_rate"] = 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting AstraDB stats: {e}")
            return {
                "total_records": 0,
                "error": str(e)
            }
    
    def clear_collection(self) -> bool:
        """Clear all documents from the collection"""
        if not self.initialize_collection():
            logger.warning("AstraDB not available, cannot clear collection")
            return False
        
        try:
            # Delete all documents using correct AstraDB method
            result = self.collection.delete_many({})
            
            deleted_count = result.deleted_count if hasattr(result, 'deleted_count') else 0
            logger.info(f"Cleared {deleted_count} documents from AstraDB collection")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing AstraDB collection: {e}")
            return False


# Global instance
astra_store = AstraDBVectorStore()

# ============================================================================
# COMPATIBILITY FUNCTIONS (for existing codebase)
# ============================================================================

def add_to_memory(token_address: str, data: Dict[str, Any]) -> str:
    """Add token information to vector store - compatibility function"""
    return astra_store.add_trading_experience(token_address, data)

def search_memory(query: str, n_results: int = 5, filter_metadata: Optional[Dict] = None) -> List[Dict[str, Any]]:
    """Search vector memory - compatibility function"""
    return astra_store.search_similar_experiences(query, n_results, filter_metadata)

def get_memory_stats() -> Dict[str, Any]:
    """Get memory statistics - compatibility function"""
    return astra_store.get_stats()

def clear_memory() -> bool:
    """Clear memory - compatibility function"""
    return astra_store.clear_collection()

def is_vector_store_available() -> bool:
    """Check if vector store is available - compatibility function"""
    return astra_store.initialize_collection()

def find_similar_tokens(token_data: Dict[str, Any], n_results: int = 5) -> List[Dict[str, Any]]:
    """Find similar tokens - compatibility function"""
    return astra_store.find_similar_tokens(token_data, n_results)

def get_vector_store_info() -> Dict[str, Any]:
    """Get vector store information - compatibility function"""
    return {
        "type": "AstraDB",
        "available": is_vector_store_available(),
        "initialized": _initialized,
        "initialization_failed": _initialization_failed,
        "collection_name": COLLECTION_NAME,
        "endpoint": ASTRA_DB_API_ENDPOINT,
        "embedding_provider": "VoyageAI" if VOYAGEAI_API_KEY else ("OpenAI" if OPENAI_API_KEY else "Hash"),
        "embedding_dimension": EMBEDDING_DIMENSION
    }

# ============================================================================
# NEW AI TRADING SPECIFIC FUNCTIONS
# ============================================================================

def add_trading_experience(token_address: str, trading_data: Dict[str, Any]) -> str:
    """Add trading experience for AI learning"""
    return astra_store.add_trading_experience(token_address, trading_data)

def search_trading_experiences(query: str, limit: int = 5, filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
    """Search for similar trading experiences"""
    return astra_store.search_similar_experiences(query, limit, filters)

def get_trading_patterns(pattern_type: str = "profitable") -> List[Dict[str, Any]]:
    """Get trading patterns for AI analysis"""
    return astra_store.get_trading_patterns(pattern_type)

def learn_from_similar_trades(current_token_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find similar historical trades for AI learning"""
    return astra_store.find_similar_tokens(current_token_data, 10)# src/memory/astra_vector_store.py
"""
AstraDB Vector Memory Store with VoyageAI Embeddings - FIXED VERSION
Uses correct DataAPIClient approach as per AstraDB documentation
"""
import os
import json
import logging
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests
import voyageai

# Configure logger
logger = logging.getLogger("trading_agent.astra_vector_store")

# Load environment variables
load_dotenv()

# Configuration
ASTRA_DB_APPLICATION_TOKEN = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
ASTRA_DB_API_ENDPOINT = os.getenv("ASTRA_DB_API_ENDPOINT")
VOYAGEAI_API_KEY = os.getenv("VOYAGEAI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Fallback

# Collection configuration
COLLECTION_NAME = "pure_ai_trading_memory"
EMBEDDING_DIMENSION = 1024  # Voyage AI embedding dimension

# Global variables
_initialized = False
_initialization_failed = False
_db_client = None
_collection = None

class AstraDBVectorStore:
    """AstraDB Vector Store with VoyageAI embeddings - Fixed Implementation"""
    
    def __init__(self):
        self.token = ASTRA_DB_APPLICATION_TOKEN
        self.endpoint = ASTRA_DB_API_ENDPOINT
        self.voyageai_key = VOYAGEAI_API_KEY
        self.openai_key = OPENAI_API_KEY
        self.collection_name = COLLECTION_NAME
        self.client = None
        self.db = None
        self.collection = None
        
        if self.token and self.endpoint:
            logger.info("AstraDB client initialized with correct credentials")
        else:
            logger.warning("AstraDB client initialized without proper credentials")
    
    def _get_voyageai_embedding(self, text: str) -> List[float]:
        """Get high-quality embedding from VoyageAI - FIXED VERSION"""
        if not self.voyageai_key:
            logger.warning("No VoyageAI API key, falling back to OpenAI")
            return self._get_openai_embedding(text)
        
        try:
            vo = voyageai.Client(api_key=self.voyageai_key)
            
            # FIXED: Correct API call according to documentation
            result = vo.embed(
                texts=[text],  # Must be a list
                model="voyage-3.5",
                input_type="document"
            )
            
            # FIXED: Correct way to access embeddings
            if result and result.embeddings:
                embedding = result.embeddings[0]  # Get first (and only) embedding
                logger.debug(f"Generated VoyageAI embedding of dimension {len(embedding)}")
                return embedding
            else:
                logger.error(f"VoyageAI API returned no embeddings for text: {text[:100]}...")
                return self._get_openai_embedding(text)

        except Exception as e:
            logger.error(f"Error getting VoyageAI embedding: {e}")
            return self._get_openai_embedding(text)
    
    def _get_openai_embedding(self, text: str) -> List[float]:
        """Fallback to OpenAI embeddings if VoyageAI fails"""
        if not self.openai_key:
            logger.warning("No OpenAI API key, using simple hash embedding")
            return self._get_hash_embedding(text)
        
        try:
            import openai
            client = openai.OpenAI(api_key=self.openai_key)
            response = client.embeddings.create(
                input=text,
                model="text-embedding-ada-002"
            )
            embedding = response.data[0].embedding
            
            # Pad or truncate to match VoyageAI dimension
            if len(embedding) > EMBEDDING_DIMENSION:
                embedding = embedding[:EMBEDDING_DIMENSION]
            elif len(embedding) < EMBEDDING_DIMENSION:
                embedding.extend([0.0] * (EMBEDDING_DIMENSION - len(embedding)))
            
            logger.debug(f"Generated OpenAI embedding (padded to {EMBEDDING_DIMENSION})")
            return embedding
            
        except Exception as e:
            logger.error(f"Error getting OpenAI embedding: {e}")
            return self._get_hash_embedding(text)
    
    def _get_hash_embedding(self, text: str) -> List[float]:
        """Simple hash-based embedding as last resort"""
        import hashlib
        hash_obj = hashlib.sha256(text.encode())
        hash_int = int(hash_obj.hexdigest(), 16)
        
        embedding = []
        for i in range(EMBEDDING_DIMENSION):
            embedding.append(((hash_int >> (i % 256)) & 1) * 2.0 - 1.0)
        
        logger.debug(f"Generated hash-based embedding of dimension {EMBEDDING_DIMENSION}")
        return embedding
    
    def initialize_collection(self) -> bool:
        """Initialize AstraDB connection using the CORRECT DataAPIClient method"""
        global _initialized, _initialization_failed, _db_client, _collection
        
        if _initialized and _collection is not None:
            self.collection = _collection
            return True
        
        if _initialization_failed:
            return False
        
        if not self.token or not self.endpoint:
            logger.error("Missing AstraDB credentials - ASTRA_DB_APPLICATION_TOKEN or ASTRA_DB_API_ENDPOINT not set")
            _initialization_failed = True
            return False
        
        try:
            # Import AstraDB client
            try:
                from astrapy import DataAPIClient
                from astrapy.info import CollectionDefinition
                from astrapy.constants import VectorMetric
            except ImportError:
                logger.error("astrapy library not installed. Run: pip install astrapy")
                _initialization_failed = True
                return False
            
            # FIXED: Initialize the client using the correct method
            logger.info("Initializing AstraDB DataAPIClient...")
            client = DataAPIClient(self.token)
            
            # FIXED: Get database by API endpoint using the correct method
            logger.info(f"Connecting to AstraDB at: {self.endpoint}")
            db = client.get_database(self.endpoint)
            
            # Test connection by listing collections
            try:
                existing_collections = db.list_collection_names()
                logger.info(f"Connected to AstraDB successfully. Existing collections: {existing_collections}")
            except Exception as e:
                logger.error(f"Failed to list collections: {e}")
                _initialization_failed = True
                return False
            
            # Check if our collection exists
            if self.collection_name not in existing_collections:
                logger.info(f"Creating collection '{self.collection_name}' with {EMBEDDING_DIMENSION}D vectors")
                
                # FIXED: Create collection with vector configuration using CollectionDefinition
                collection_definition = (
                    CollectionDefinition.builder()
                    .set_vector_dimension(EMBEDDING_DIMENSION)
                    .set_vector_metric(VectorMetric.COSINE)
                    .build()
                )
                
                collection = db.create_collection(
                    self.collection_name,
                    definition=collection_definition
                )
                
                logger.info(f"Created collection '{self.collection_name}' successfully")
            else:
                # Get existing collection
                collection = db.get_collection(self.collection_name)
                logger.info(f"Connected to existing collection '{self.collection_name}'")
            
            # Store references globally
            _db_client = client
            _collection = collection
            self.client = client
            self.db = db
            self.collection = collection
            
            _initialized = True
            logger.info("AstraDB initialization completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing AstraDB: {e}")
            _initialization_failed = True
            return False
    
    def add_trading_experience(self, token_address: str, trading_data: Dict[str, Any]) -> str:
        """Add trading experience to vector memory for AI learning"""
        if not self.initialize_collection():
            logger.warning("AstraDB not available, skipping experience storage")
            return ""
        
        try:
            # Generate document ID
            doc_id = str(uuid.uuid4())
            timestamp = datetime.now().isoformat()
            
            # Create rich document text for embedding (trading-focused)
            token_symbol = trading_data.get("token_symbol", "unknown")
            trade_type = trading_data.get("trade_type", "analysis")
            profit_pct = trading_data.get("profit_percentage", 0)
            ai_reasoning = trading_data.get("ai_reasoning", "")
            market_conditions = trading_data.get("market_conditions", {})
            
            # Create comprehensive text for semantic search
            document_text = f"""
            Token Analysis: {token_symbol} ({token_address})
            Trade Type: {trade_type}
            Performance: {profit_pct:+.1f}% profit
            Market Conditions: {json.dumps(market_conditions)}
            AI Reasoning: {ai_reasoning}
            
            Key Metrics:
            Safety Score: {trading_data.get('safety_score', 0):.1f}
            Social Activity: {trading_data.get('social_activity', 0):.1f}
            Viral Score: {trading_data.get('viral_score', 0):.1f}
            Market Health: {trading_data.get('market_health_score', 0):.1f}
            
            Trade Details:
            Entry Price: ${trading_data.get('entry_price_usd', 0):.6f}
            Exit Price: ${trading_data.get('exit_price_usd', 0):.6f}
            Hold Time: {trading_data.get('hold_time_hours', 0):.1f} hours
            Position Size: {trading_data.get('position_size_sol', 0):.4f} SOL
            
            Lessons Learned: {trading_data.get('lessons_learned', '')}
            Strategy Used: {trading_data.get('strategy', 'unknown')}
            Success Factors: {json.dumps(trading_data.get('success_factors', []))}
            Risk Factors: {json.dumps(trading_data.get('risk_factors', []))}
            """
            
            # Get high-quality embedding
            embedding = self._get_voyageai_embedding(document_text)
            
            # Prepare document with rich metadata for filtering
            document = {
                "_id": doc_id,
                "document_type": "trading_experience",
                "token_address": token_address,
                "token_symbol": token_symbol,
                "timestamp": timestamp,
                
                # Trading metadata
                "trade_type": trade_type,
                "profit_percentage": profit_pct,
                "was_profitable": profit_pct > 0,
                "position_size_sol": trading_data.get("position_size_sol", 0),
                "hold_time_hours": trading_data.get("hold_time_hours", 0),
                "strategy": trading_data.get("strategy", "unknown"),
                
                # Performance metrics
                "safety_score": trading_data.get("safety_score", 0),
                "social_activity": trading_data.get("social_activity", 0),
                "viral_score": trading_data.get("viral_score", 0),
                "market_health_score": trading_data.get("market_health_score", 0),
                "overall_score": trading_data.get("overall_score", 0),
                
                # Market context
                "market_sentiment": market_conditions.get("sentiment", "neutral"),
                "market_volatility": market_conditions.get("volatility", "medium"),
                
                # Content
                "document_text": document_text,
                "ai_reasoning": ai_reasoning,
                "complete_trading_data": trading_data,
                
                # Vector embedding
                "$vector": embedding
            }
            
            # Insert document using correct AstraDB method
            result = self.collection.insert_one(document)
            
            if result and result.inserted_id:
                logger.info(f"Added trading experience for {token_symbol} to vector memory: {doc_id}")
                return doc_id
            else:
                logger.error(f"Failed to insert trading experience: {result}")
                return ""
                
        except Exception as e:
            logger.error(f"Error adding trading experience to vector memory: {e}")
            return ""
    
    def search_similar_experiences(self, query: str, limit: int = 5, filter_criteria: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Search for similar trading experiences using semantic similarity"""
        if not self.initialize_collection():
            logger.warning("AstraDB not available, returning empty results")
            return []
        
        try:
            # Get query embedding
            query_embedding = self._get_voyageai_embedding(query)
            
            # Prepare search with vector similarity
            search_kwargs = {
                "sort": {"$vector": query_embedding},
                "limit": limit,
                "include_similarity": True
            }
            
            # Add filter if provided
            if filter_criteria:
                search_kwargs["filter"] = filter_criteria
            
            # Execute search using correct AstraDB method
            cursor = self.collection.find(**search_kwargs)
            
            processed_results = []
            for doc in cursor:
                processed_results.append({
                    "id": doc.get("_id"),
                    "similarity": doc.get("$similarity", 0.0),
                    "metadata": {
                        "token_address": doc.get("token_address"),
                        "token_symbol": doc.get("token_symbol"),
                        "trade_type": doc.get("trade_type"),
                        "profit_percentage": doc.get("profit_percentage"),
                        "was_profitable": doc.get("was_profitable"),
                        "strategy": doc.get("strategy"),
                        "timestamp": doc.get("timestamp"),
                        "hold_time_hours": doc.get("hold_time_hours"),
                        "overall_score": doc.get("overall_score"),
                        "market_sentiment": doc.get("market_sentiment")
                    },
                    "ai_reasoning": doc.get("ai_reasoning", ""),
                    "trading_data": doc.get("complete_trading_data", {}),
                    "document": doc.get("document_text", "")
                })
            
            logger.info(f"Vector search for '{query}' returned {len(processed_results)} similar experiences")
            return processed_results
            
        except Exception as e:
            logger.error(f"Error searching vector memory: {e}")
            return []
    
    def find_similar_tokens(self, token_data: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
        """Find similar tokens based on characteristics"""
        try:
            # Create search query based on token characteristics
            query_parts = []
            
            if token_data.get("symbol"):
                query_parts.append(f"Token similar to {token_data['symbol']}")
            
            if token_data.get("safety_score", 0) > 0:
                query_parts.append(f"Safety score around {token_data['safety_score']:.0f}")
            
            if token_data.get("social_activity", 0) > 0:
                query_parts.append(f"Social activity {token_data['social_activity']:.0f}")
            
            if token_data.get("market_cap", 0) > 0:
                query_parts.append(f"Market cap ${token_data['market_cap']:,.0f}")
            
            if token_data.get("liquidity_usd", 0) > 0:
                query_parts.append(f"Liquidity ${token_data['liquidity_usd']:,.0f}")
            
            query = ". ".join(query_parts)
            
            # Search for similar experiences
            results = self.search_similar_experiences(query, limit)
            
            # Extract token data from results
            similar_tokens = []
            for result in results:
                trading_data = result.get("trading_data", {})
                if trading_data:
                    similar_tokens.append({
                        "token_symbol": result["metadata"]["token_symbol"],
                        "token_address": result["metadata"]["token_address"],
                        "similarity_score": result["similarity"],
                        "profit_achieved": result["metadata"]["profit_percentage"],
                        "strategy_used": result["metadata"]["strategy"],
                        "ai_reasoning": result["ai_reasoning"],
                        "characteristics": {
                            "safety_score": trading_data.get("safety_score", 0),
                            "social_activity": trading_data.get("social_activity", 0),
                            "viral_score": trading_data.get("viral_score", 0),
                            "market_health": trading_data.get("market_health_score", 0)
                        }
                    })
            
            return similar_tokens
            
        except Exception as e:
            logger.error(f"Error finding similar tokens: {e}")
            return []
    
    def get_trading_patterns(self, pattern_type: str = "profitable") -> List[Dict[str, Any]]:
        """Get trading patterns for AI learning"""
        try:
            filter_criteria = {}
            
            if pattern_type == "profitable":
                filter_criteria["was_profitable"] = True
            elif pattern_type == "losing":
                filter_criteria["was_profitable"] = False
            elif pattern_type == "high_profit":
                filter_criteria = {"profit_percentage": {"$gte": 20}}
            elif pattern_type == "quick_trades":
                filter_criteria = {"hold_time_hours": {"$lte": 2}}
            
            # Search for patterns
            query = f"Trading patterns for {pattern_type} trades with market analysis"
            results = self.search_similar_experiences(query, limit=20, filter_criteria=filter_criteria)
            
            return results
            
        except Exception as e:
            logger.error(f"Error getting trading patterns: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        if not self.initialize_collection():
            return {
                "total_records": 0,
                "error": "AstraDB not available"
            }
        
        try:
            # Count documents using correct AstraDB method
            count = self.collection.count_documents({})
            
            # Get some sample statistics
            stats = {
                "total_records": count,
                "collection_name": self.collection_name,
                "endpoint": self.endpoint,
                "embedding_dimension": EMBEDDING_DIMENSION,
                "embedding_provider": "VoyageAI" if self.voyageai_key else ("OpenAI" if self.openai_key else "Hash"),
                "timestamp": datetime.now().isoformat(),
                "status": "healthy"
            }
            
            # Get profitable vs losing trades
            if count > 0:
                try:
                    profitable_count = self.collection.count_documents({"was_profitable": True})
                    stats["profitable_trades"] = profitable_count
                    stats["losing_trades"] = count - profitable_count
                    stats["win_rate"] = profitable_count / count if count > 0 else 0
                except:
                    stats["win_rate"] = 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting AstraDB stats: {e}")
            return {
                "total_records": 0,
                "error": str(e)
            }
    
    def clear_collection(self) -> bool:
        """Clear all documents from the collection"""
        if not self.initialize_collection():
            logger.warning("AstraDB not available, cannot clear collection")
            return False
        
        try:
            # Delete all documents using correct AstraDB method
            result = self.collection.delete_many({})
            
            deleted_count = result.deleted_count if hasattr(result, 'deleted_count') else 0
            logger.info(f"Cleared {deleted_count} documents from AstraDB collection")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing AstraDB collection: {e}")
            return False


# Global instance
astra_store = AstraDBVectorStore()

# ============================================================================
# COMPATIBILITY FUNCTIONS (for existing codebase)
# ============================================================================

def add_to_memory(token_address: str, data: Dict[str, Any]) -> str:
    """Add token information to vector store - compatibility function"""
    return astra_store.add_trading_experience(token_address, data)

def search_memory(query: str, n_results: int = 5, filter_metadata: Optional[Dict] = None) -> List[Dict[str, Any]]:
    """Search vector memory - compatibility function"""
    return astra_store.search_similar_experiences(query, n_results, filter_metadata)

def get_memory_stats() -> Dict[str, Any]:
    """Get memory statistics - compatibility function"""
    return astra_store.get_stats()

def clear_memory() -> bool:
    """Clear memory - compatibility function"""
    return astra_store.clear_collection()

def is_vector_store_available() -> bool:
    """Check if vector store is available - compatibility function"""
    return astra_store.initialize_collection()

def find_similar_tokens(token_data: Dict[str, Any], n_results: int = 5) -> List[Dict[str, Any]]:
    """Find similar tokens - compatibility function"""
    return astra_store.find_similar_tokens(token_data, n_results)

def get_vector_store_info() -> Dict[str, Any]:
    """Get vector store information - compatibility function"""
    return {
        "type": "AstraDB",
        "available": is_vector_store_available(),
        "initialized": _initialized,
        "initialization_failed": _initialization_failed,
        "collection_name": COLLECTION_NAME,
        "endpoint": ASTRA_DB_API_ENDPOINT,
        "embedding_provider": "VoyageAI" if VOYAGEAI_API_KEY else ("OpenAI" if OPENAI_API_KEY else "Hash"),
        "embedding_dimension": EMBEDDING_DIMENSION
    }

# ============================================================================
# NEW AI TRADING SPECIFIC FUNCTIONS
# ============================================================================

def add_trading_experience(token_address: str, trading_data: Dict[str, Any]) -> str:
    """Add trading experience for AI learning"""
    return astra_store.add_trading_experience(token_address, trading_data)

def search_trading_experiences(query: str, limit: int = 5, filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
    """Search for similar trading experiences"""
    return astra_store.search_similar_experiences(query, limit, filters)

def get_trading_patterns(pattern_type: str = "profitable") -> List[Dict[str, Any]]:
    """Get trading patterns for AI analysis"""
    return astra_store.get_trading_patterns(pattern_type)

def learn_from_similar_trades(current_token_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find similar historical trades for AI learning"""
    return astra_store.find_similar_tokens(current_token_data, 10)# src/memory/astra_vector_store.py
"""
AstraDB Vector Memory Store with VoyageAI Embeddings - FIXED VERSION
Uses correct DataAPIClient approach as per AstraDB documentation
"""
import os
import json
import logging
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests
import voyageai

# Configure logger
logger = logging.getLogger("trading_agent.astra_vector_store")

# Load environment variables
load_dotenv()

# Configuration
ASTRA_DB_APPLICATION_TOKEN = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
ASTRA_DB_API_ENDPOINT = os.getenv("ASTRA_DB_API_ENDPOINT")
VOYAGEAI_API_KEY = os.getenv("VOYAGEAI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Fallback

# Collection configuration
COLLECTION_NAME = "pure_ai_trading_memory"
EMBEDDING_DIMENSION = 1024  # Voyage AI embedding dimension

# Global variables
_initialized = False
_initialization_failed = False
_db_client = None
_collection = None

class AstraDBVectorStore:
    """AstraDB Vector Store with VoyageAI embeddings - Fixed Implementation"""
    
    def __init__(self):
        self.token = ASTRA_DB_APPLICATION_TOKEN
        self.endpoint = ASTRA_DB_API_ENDPOINT
        self.voyageai_key = VOYAGEAI_API_KEY
        self.openai_key = OPENAI_API_KEY
        self.collection_name = COLLECTION_NAME
        self.client = None
        self.db = None
        self.collection = None
        
        if self.token and self.endpoint:
            logger.info("AstraDB client initialized with correct credentials")
        else:
            logger.warning("AstraDB client initialized without proper credentials")
    
    def _get_voyageai_embedding(self, text: str) -> List[float]:
        """Get high-quality embedding from VoyageAI - FIXED VERSION"""
        if not self.voyageai_key:
            logger.warning("No VoyageAI API key, falling back to OpenAI")
            return self._get_openai_embedding(text)
        
        try:
            vo = voyageai.Client(api_key=self.voyageai_key)
            
            # FIXED: Correct API call according to documentation
            result = vo.embed(
                texts=[text],  # Must be a list
                model="voyage-3.5",
                input_type="document"
            )
            
            # FIXED: Correct way to access embeddings
            if result and result.embeddings:
                embedding = result.embeddings[0]  # Get first (and only) embedding
                logger.debug(f"Generated VoyageAI embedding of dimension {len(embedding)}")
                return embedding
            else:
                logger.error(f"VoyageAI API returned no embeddings for text: {text[:100]}...")
                return self._get_openai_embedding(text)

        except Exception as e:
            logger.error(f"Error getting VoyageAI embedding: {e}")
            return self._get_openai_embedding(text)
    
    def _get_openai_embedding(self, text: str) -> List[float]:
        """Fallback to OpenAI embeddings if VoyageAI fails"""
        if not self.openai_key:
            logger.warning("No OpenAI API key, using simple hash embedding")
            return self._get_hash_embedding(text)
        
        try:
            import openai
            client = openai.OpenAI(api_key=self.openai_key)
            response = client.embeddings.create(
                input=text,
                model="text-embedding-ada-002"
            )
            embedding = response.data[0].embedding
            
            # Pad or truncate to match VoyageAI dimension
            if len(embedding) > EMBEDDING_DIMENSION:
                embedding = embedding[:EMBEDDING_DIMENSION]
            elif len(embedding) < EMBEDDING_DIMENSION:
                embedding.extend([0.0] * (EMBEDDING_DIMENSION - len(embedding)))
            
            logger.debug(f"Generated OpenAI embedding (padded to {EMBEDDING_DIMENSION})")
            return embedding
            
        except Exception as e:
            logger.error(f"Error getting OpenAI embedding: {e}")
            return self._get_hash_embedding(text)
    
    def _get_hash_embedding(self, text: str) -> List[float]:
        """Simple hash-based embedding as last resort"""
        import hashlib
        hash_obj = hashlib.sha256(text.encode())
        hash_int = int(hash_obj.hexdigest(), 16)
        
        embedding = []
        for i in range(EMBEDDING_DIMENSION):
            embedding.append(((hash_int >> (i % 256)) & 1) * 2.0 - 1.0)
        
        logger.debug(f"Generated hash-based embedding of dimension {EMBEDDING_DIMENSION}")
        return embedding
    
    def initialize_collection(self) -> bool:
        """Initialize AstraDB connection using the CORRECT DataAPIClient method"""
        global _initialized, _initialization_failed, _db_client, _collection
        
        if _initialized and _collection is not None:
            self.collection = _collection
            return True
        
        if _initialization_failed:
            return False
        
        if not self.token or not self.endpoint:
            logger.error("Missing AstraDB credentials - ASTRA_DB_APPLICATION_TOKEN or ASTRA_DB_API_ENDPOINT not set")
            _initialization_failed = True
            return False
        
        try:
            # Import AstraDB client
            try:
                from astrapy import DataAPIClient
                from astrapy.info import CollectionDefinition
                from astrapy.constants import VectorMetric
            except ImportError:
                logger.error("astrapy library not installed. Run: pip install astrapy")
                _initialization_failed = True
                return False
            
            # FIXED: Initialize the client using the correct method
            logger.info("Initializing AstraDB DataAPIClient...")
            client = DataAPIClient(self.token)
            
            # FIXED: Get database by API endpoint using the correct method
            logger.info(f"Connecting to AstraDB at: {self.endpoint}")
            db = client.get_database(self.endpoint)
            
            # Test connection by listing collections
            try:
                existing_collections = db.list_collection_names()
                logger.info(f"Connected to AstraDB successfully. Existing collections: {existing_collections}")
            except Exception as e:
                logger.error(f"Failed to list collections: {e}")
                _initialization_failed = True
                return False
            
            # Check if our collection exists
            if self.collection_name not in existing_collections:
                logger.info(f"Creating collection '{self.collection_name}' with {EMBEDDING_DIMENSION}D vectors")
                
                # FIXED: Create collection with vector configuration using CollectionDefinition
                collection_definition = (
                    CollectionDefinition.builder()
                    .set_vector_dimension(EMBEDDING_DIMENSION)
                    .set_vector_metric(VectorMetric.COSINE)
                    .build()
                )
                
                collection = db.create_collection(
                    self.collection_name,
                    definition=collection_definition
                )
                
                logger.info(f"Created collection '{self.collection_name}' successfully")
            else:
                # Get existing collection
                collection = db.get_collection(self.collection_name)
                logger.info(f"Connected to existing collection '{self.collection_name}'")
            
            # Store references globally
            _db_client = client
            _collection = collection
            self.client = client
            self.db = db
            self.collection = collection
            
            _initialized = True
            logger.info("AstraDB initialization completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing AstraDB: {e}")
            _initialization_failed = True
            return False
    
    def add_trading_experience(self, token_address: str, trading_data: Dict[str, Any]) -> str:
        """Add trading experience to vector memory for AI learning"""
        if not self.initialize_collection():
            logger.warning("AstraDB not available, skipping experience storage")
            return ""
        
        try:
            # Generate document ID
            doc_id = str(uuid.uuid4())
            timestamp = datetime.now().isoformat()
            
            # Create rich document text for embedding (trading-focused)
            token_symbol = trading_data.get("token_symbol", "unknown")
            trade_type = trading_data.get("trade_type", "analysis")
            profit_pct = trading_data.get("profit_percentage", 0)
            ai_reasoning = trading_data.get("ai_reasoning", "")
            market_conditions = trading_data.get("market_conditions", {})
            
            # Create comprehensive text for semantic search
            document_text = f"""
            Token Analysis: {token_symbol} ({token_address})
            Trade Type: {trade_type}
            Performance: {profit_pct:+.1f}% profit
            Market Conditions: {json.dumps(market_conditions)}
            AI Reasoning: {ai_reasoning}
            
            Key Metrics:
            Safety Score: {trading_data.get('safety_score', 0):.1f}
            Social Activity: {trading_data.get('social_activity', 0):.1f}
            Viral Score: {trading_data.get('viral_score', 0):.1f}
            Market Health: {trading_data.get('market_health_score', 0):.1f}
            
            Trade Details:
            Entry Price: ${trading_data.get('entry_price_usd', 0):.6f}
            Exit Price: ${trading_data.get('exit_price_usd', 0):.6f}
            Hold Time: {trading_data.get('hold_time_hours', 0):.1f} hours
            Position Size: {trading_data.get('position_size_sol', 0):.4f} SOL
            
            Lessons Learned: {trading_data.get('lessons_learned', '')}
            Strategy Used: {trading_data.get('strategy', 'unknown')}
            Success Factors: {json.dumps(trading_data.get('success_factors', []))}
            Risk Factors: {json.dumps(trading_data.get('risk_factors', []))}
            """
            
            # Get high-quality embedding
            embedding = self._get_voyageai_embedding(document_text)
            
            # Prepare document with rich metadata for filtering
            document = {
                "_id": doc_id,
                "document_type": "trading_experience",
                "token_address": token_address,
                "token_symbol": token_symbol,
                "timestamp": timestamp,
                
                # Trading metadata
                "trade_type": trade_type,
                "profit_percentage": profit_pct,
                "was_profitable": profit_pct > 0,
                "position_size_sol": trading_data.get("position_size_sol", 0),
                "hold_time_hours": trading_data.get("hold_time_hours", 0),
                "strategy": trading_data.get("strategy", "unknown"),
                
                # Performance metrics
                "safety_score": trading_data.get("safety_score", 0),
                "social_activity": trading_data.get("social_activity", 0),
                "viral_score": trading_data.get("viral_score", 0),
                "market_health_score": trading_data.get("market_health_score", 0),
                "overall_score": trading_data.get("overall_score", 0),
                
                # Market context
                "market_sentiment": market_conditions.get("sentiment", "neutral"),
                "market_volatility": market_conditions.get("volatility", "medium"),
                
                # Content
                "document_text": document_text,
                "ai_reasoning": ai_reasoning,
                "complete_trading_data": trading_data,
                
                # Vector embedding
                "$vector": embedding
            }
            
            # Insert document using correct AstraDB method
            result = self.collection.insert_one(document)
            
            if result and result.inserted_id:
                logger.info(f"Added trading experience for {token_symbol} to vector memory: {doc_id}")
                return doc_id
            else:
                logger.error(f"Failed to insert trading experience: {result}")
                return ""
                
        except Exception as e:
            logger.error(f"Error adding trading experience to vector memory: {e}")
            return ""
    
    def search_similar_experiences(self, query: str, limit: int = 5, filter_criteria: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Search for similar trading experiences using semantic similarity"""
        if not self.initialize_collection():
            logger.warning("AstraDB not available, returning empty results")
            return []
        
        try:
            # Get query embedding
            query_embedding = self._get_voyageai_embedding(query)
            
            # Prepare search with vector similarity
            search_kwargs = {
                "sort": {"$vector": query_embedding},
                "limit": limit,
                "include_similarity": True
            }
            
            # Add filter if provided
            if filter_criteria:
                search_kwargs["filter"] = filter_criteria
            
            # Execute search using correct AstraDB method
            cursor = self.collection.find(**search_kwargs)
            
            processed_results = []
            for doc in cursor:
                processed_results.append({
                    "id": doc.get("_id"),
                    "similarity": doc.get("$similarity", 0.0),
                    "metadata": {
                        "token_address": doc.get("token_address"),
                        "token_symbol": doc.get("token_symbol"),
                        "trade_type": doc.get("trade_type"),
                        "profit_percentage": doc.get("profit_percentage"),
                        "was_profitable": doc.get("was_profitable"),
                        "strategy": doc.get("strategy"),
                        "timestamp": doc.get("timestamp"),
                        "hold_time_hours": doc.get("hold_time_hours"),
                        "overall_score": doc.get("overall_score"),
                        "market_sentiment": doc.get("market_sentiment")
                    },
                    "ai_reasoning": doc.get("ai_reasoning", ""),
                    "trading_data": doc.get("complete_trading_data", {}),
                    "document": doc.get("document_text", "")
                })
            
            logger.info(f"Vector search for '{query}' returned {len(processed_results)} similar experiences")
            return processed_results
            
        except Exception as e:
            logger.error(f"Error searching vector memory: {e}")
            return []
    
    def find_similar_tokens(self, token_data: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
        """Find similar tokens based on characteristics"""
        try:
            # Create search query based on token characteristics
            query_parts = []
            
            if token_data.get("symbol"):
                query_parts.append(f"Token similar to {token_data['symbol']}")
            
            if token_data.get("safety_score", 0) > 0:
                query_parts.append(f"Safety score around {token_data['safety_score']:.0f}")
            
            if token_data.get("social_activity", 0) > 0:
                query_parts.append(f"Social activity {token_data['social_activity']:.0f}")
            
            if token_data.get("market_cap", 0) > 0:
                query_parts.append(f"Market cap ${token_data['market_cap']:,.0f}")
            
            if token_data.get("liquidity_usd", 0) > 0:
                query_parts.append(f"Liquidity ${token_data['liquidity_usd']:,.0f}")
            
            query = ". ".join(query_parts)
            
            # Search for similar experiences
            results = self.search_similar_experiences(query, limit)
            
            # Extract token data from results
            similar_tokens = []
            for result in results:
                trading_data = result.get("trading_data", {})
                if trading_data:
                    similar_tokens.append({
                        "token_symbol": result["metadata"]["token_symbol"],
                        "token_address": result["metadata"]["token_address"],
                        "similarity_score": result["similarity"],
                        "profit_achieved": result["metadata"]["profit_percentage"],
                        "strategy_used": result["metadata"]["strategy"],
                        "ai_reasoning": result["ai_reasoning"],
                        "characteristics": {
                            "safety_score": trading_data.get("safety_score", 0),
                            "social_activity": trading_data.get("social_activity", 0),
                            "viral_score": trading_data.get("viral_score", 0),
                            "market_health": trading_data.get("market_health_score", 0)
                        }
                    })
            
            return similar_tokens
            
        except Exception as e:
            logger.error(f"Error finding similar tokens: {e}")
            return []
        
    
    def get_trading_patterns(self, pattern_type: str = "profitable") -> List[Dict[str, Any]]:
        """Get trading patterns for AI learning"""
        try:
            filter_criteria = {}
            
            if pattern_type == "profitable":
                filter_criteria["was_profitable"] = True
            elif pattern_type == "losing":
                filter_criteria["was_profitable"] = False
            elif pattern_type == "high_profit":
                filter_criteria = {"profit_percentage": {"$gte": 20}}
            elif pattern_type == "quick_trades":
                filter_criteria = {"hold_time_hours": {"$lte": 2}}
            
            # Search for patterns
            query = f"Trading patterns for {pattern_type} trades with market analysis"
            results = self.search_similar_experiences(query, limit=20, filter_criteria=filter_criteria)
            
            return results
            
        except Exception as e:
            logger.error(f"Error getting trading patterns: {e}")
            return []
        
    
    def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics - FIXED VERSION"""
        if not self.initialize_collection():
            return {
                "total_records": 0,
                "error": "AstraDB not available"
            }
        
        try:
            # FIXED: Use upper_bound parameter as required by AstraDB API
            count = self.collection.count_documents({}, upper_bound=1000)
            
            # Get some sample statistics
            stats = {
                "total_records": count,
                "collection_name": self.collection_name,
                "endpoint": self.endpoint,
                "embedding_dimension": EMBEDDING_DIMENSION,
                "embedding_provider": "VoyageAI" if self.voyageai_key else ("OpenAI" if self.openai_key else "Hash"),
                "timestamp": datetime.now().isoformat(),
                "status": "healthy"
            }
            
            # Get profitable vs losing trades if we have records
            if count > 0:
                try:
                    # FIXED: Also add upper_bound here
                    profitable_count = self.collection.count_documents(
                        {"was_profitable": True}, 
                        upper_bound=1000
                    )
                    stats["profitable_trades"] = profitable_count
                    stats["losing_trades"] = count - profitable_count
                    stats["win_rate"] = profitable_count / count if count > 0 else 0
                except Exception as e:
                    logger.warning(f"Could not get detailed trade stats: {e}")
                    stats["win_rate"] = 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting AstraDB stats: {e}")
            return {
                "total_records": 0,
                "error": str(e)
            }

    def clear_collection(self) -> bool:
        """Clear all documents from the collection - FIXED VERSION"""
        if not self.initialize_collection():
            logger.warning("AstraDB not available, cannot clear collection")
            return False
        
        try:
            # FIXED: Use delete_many with proper syntax
            result = self.collection.delete_many({})
            
            # The result might not have deleted_count attribute in newer versions
            deleted_count = getattr(result, 'deleted_count', 0)
            if deleted_count == 0:
                # Try to get count before and after to estimate
                logger.info("Cleared collection (count not available)")
            else:
                logger.info(f"Cleared {deleted_count} documents from AstraDB collection")
            
            return True
            
        except Exception as e:
            logger.error(f"Error clearing AstraDB collection: {e}")
            return False


# Global instance
astra_store = AstraDBVectorStore()

# ============================================================================
# COMPATIBILITY FUNCTIONS (for existing codebase)
# ============================================================================

def add_to_memory(token_address: str, data: Dict[str, Any]) -> str:
    """Add token information to vector store - compatibility function"""
    return astra_store.add_trading_experience(token_address, data)

def search_memory(query: str, n_results: int = 5, filter_metadata: Optional[Dict] = None) -> List[Dict[str, Any]]:
    """Search vector memory - compatibility function"""
    return astra_store.search_similar_experiences(query, n_results, filter_metadata)

def get_memory_stats() -> Dict[str, Any]:
    """Get memory statistics - compatibility function"""
    return astra_store.get_stats()

def clear_memory() -> bool:
    """Clear memory - compatibility function"""
    return astra_store.clear_collection()

def is_vector_store_available() -> bool:
    """Check if vector store is available - compatibility function"""
    return astra_store.initialize_collection()

def find_similar_tokens(token_data: Dict[str, Any], n_results: int = 5) -> List[Dict[str, Any]]:
    """Find similar tokens - compatibility function"""
    return astra_store.find_similar_tokens(token_data, n_results)

def get_vector_store_info() -> Dict[str, Any]:
    """Get vector store information - compatibility function"""
    return {
        "type": "AstraDB",
        "available": is_vector_store_available(),
        "initialized": _initialized,
        "initialization_failed": _initialization_failed,
        "collection_name": COLLECTION_NAME,
        "endpoint": ASTRA_DB_API_ENDPOINT,
        "embedding_provider": "VoyageAI" if VOYAGEAI_API_KEY else ("OpenAI" if OPENAI_API_KEY else "Hash"),
        "embedding_dimension": EMBEDDING_DIMENSION
    }

# ============================================================================
# NEW AI TRADING SPECIFIC FUNCTIONS
# ============================================================================

def add_trading_experience(token_address: str, trading_data: Dict[str, Any]) -> str:
    """Add trading experience for AI learning"""
    return astra_store.add_trading_experience(token_address, trading_data)

def search_trading_experiences(query: str, limit: int = 5, filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
    """Search for similar trading experiences"""
    return astra_store.search_similar_experiences(query, limit, filters)

def get_trading_patterns(pattern_type: str = "profitable") -> List[Dict[str, Any]]:
    """Get trading patterns for AI analysis"""
    return astra_store.get_trading_patterns(pattern_type)

def learn_from_similar_trades(current_token_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find similar historical trades for AI learning"""
    return astra_store.find_similar_tokens(current_token_data, 10)