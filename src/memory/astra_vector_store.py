# src/memory/astra_vector_store.py
"""
AstraDB Vector Memory Store with Model-Specific Collections
Supports both Claude+VoyageAI and Gemini+Google embeddings in separate collections
"""
import os
import json
import logging
import time
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests
import voyageai
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# Configure logger
logger = logging.getLogger("trading_agent.astra_vector_store")

# Load environment variables
load_dotenv()

# Configuration
ASTRA_DB_APPLICATION_TOKEN = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
ASTRA_DB_API_ENDPOINT = os.getenv("ASTRA_DB_API_ENDPOINT")
VOYAGEAI_API_KEY = os.getenv("VOYAGEAI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Fallback
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")  # Google Gemini support

# Collection configuration - Model-specific collections
CLAUDE_COLLECTION_NAME = "claude_trading_memory"
GEMINI_COLLECTION_NAME = "gemini_trading_memory"
EMBEDDING_DIMENSION = 1024  # Consistent dimension across all models

# Collection name mapping
COLLECTION_MAP = {
    "anthropic": CLAUDE_COLLECTION_NAME,
    "voyageai": CLAUDE_COLLECTION_NAME,  # VoyageAI paired with Claude
    "google": GEMINI_COLLECTION_NAME
}

# Global variables - Now track multiple collections
_initialized = {}  # Track initialization per model
_initialization_failed_at = {}  # {model_provider: float timestamp} — time-based backoff, not permanent flag
INIT_RETRY_AFTER_SECONDS = 60  # Retry failed initializations after 60s
_db_client = None
_db = None  # Cached database object (get_database() result)
_collections = {}  # Store multiple collections
_current_model_provider = "voyageai"  # Global context for current model provider

def get_collection_name(model_provider: str) -> str:
    """Get the appropriate collection name for the given model provider"""
    return COLLECTION_MAP.get(model_provider, CLAUDE_COLLECTION_NAME)

class AstraDBVectorStore:
    """AstraDB Vector Store with Model-Specific Collections"""
    
    def __init__(self):
        self.token = ASTRA_DB_APPLICATION_TOKEN
        self.endpoint = ASTRA_DB_API_ENDPOINT
        self.voyageai_key = VOYAGEAI_API_KEY
        self.openai_key = OPENAI_API_KEY
        self.google_key = GOOGLE_API_KEY
        self.client = None
        self.db = None
        
        if self.token and self.endpoint:
            logger.info("AstraDB client initialized with correct credentials")
            self._check_connectivity()
            # Eagerly warm up both collections so first trading cycle has no cold-start delay
            for _provider in ("anthropic", "google"):
                try:
                    self.get_collection_for_model(_provider)
                except Exception:
                    pass  # errors already logged inside get_collection_for_model
        else:
            logger.warning("AstraDB client initialized without proper credentials — set ASTRA_DB_APPLICATION_TOKEN and ASTRA_DB_API_ENDPOINT in .env")
    
    def _check_connectivity(self):
        """Verify AstraDB hostname resolves at startup. Logs a clear error if DB is down."""
        import socket
        try:
            from urllib.parse import urlparse
            host = urlparse(self.endpoint).hostname
            socket.getaddrinfo(host, 443)
            logger.info(f"AstraDB connectivity OK — {host} resolves")
        except Exception as e:
            logger.error(
                f"⚠️  AstraDB UNREACHABLE: {e}\n"
                "   → Vector memory will be unavailable until the DB is restored.\n"
                "   → Log in to astra.datastax.com, Resume/recreate the database,\n"
                "     then update ASTRA_DB_API_ENDPOINT in .env if the URL changed."
            )

    def get_embedding(self, text: str, model_provider: str = "voyageai", task_type: str = "RETRIEVAL_DOCUMENT", input_type: str = "document") -> List[float]:
        """Smart embedding provider selection based on model choice."""
        if model_provider == "google" and self.google_key:
            return self._get_gemini_embedding(text, task_type)
        elif model_provider == "voyageai" or model_provider == "anthropic":
            return self._get_voyageai_embedding(text, input_type=input_type)
        else:
            # Fallback logic
            if self.voyageai_key:
                return self._get_voyageai_embedding(text, input_type=input_type)
            elif self.google_key:
                return self._get_gemini_embedding(text, task_type)
            else:
                return self._get_openai_embedding(text)
    
    def _get_gemini_embedding(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> List[float]:
        """Get embedding from Google Gemini - optimized for RAG"""
        try:
            embeddings_model = GoogleGenerativeAIEmbeddings(
                model="models/gemini-embedding-001",
                google_api_key=self.google_key,
                task_type=task_type,
                output_dimensionality=1024  # Match VoyageAI dimension
            )

            embedding = embeddings_model.embed_query(text)

            # Ensure consistent dimension
            if len(embedding) != EMBEDDING_DIMENSION:
                if len(embedding) < EMBEDDING_DIMENSION:
                    embedding.extend([0.0] * (EMBEDDING_DIMENSION - len(embedding)))
                elif len(embedding) > EMBEDDING_DIMENSION:
                    embedding = embedding[:EMBEDDING_DIMENSION]

            logger.debug(f"Generated Gemini embedding with {len(embedding)} dimensions")
            return embedding

        except Exception as e:
            logger.error(f"Error getting Gemini embedding: {e}")
            # Fallback to VoyageAI if available
            if self.voyageai_key:
                return self._get_voyageai_embedding(text)
            else:
                return self._get_openai_embedding(text)
    
    def _get_voyageai_embedding(self, text: str, input_type: str = "document") -> List[float]:
        """Get high-quality embedding from VoyageAI (voyage-4)."""
        if not self.voyageai_key:
            logger.warning("No VoyageAI API key, falling back to OpenAI")
            return self._get_openai_embedding(text)

        try:
            vo = voyageai.Client(api_key=self.voyageai_key)

            result = vo.embed(
                texts=[text],
                model="voyage-4",
                input_type=input_type,
                output_dimension=1024,
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
        """Fallback to OpenAI embeddings if other methods fail"""
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
    
    def get_collection_for_model(self, model_provider: str):
        """Get or initialize collection for specific model provider"""
        global _db_client, _collections, _initialized, _initialization_failed
        
        collection_name = get_collection_name(model_provider)
        
        # Return existing collection if already initialized
        if collection_name in _collections:
            return _collections[collection_name]
        
        # Check if this model recently failed — retry after INIT_RETRY_AFTER_SECONDS
        failed_at = _initialization_failed_at.get(model_provider)
        if failed_at and (time.time() - failed_at) < INIT_RETRY_AFTER_SECONDS:
            return None

        # Initialize if needed
        if not _db_client:
            if not self._initialize_db_client():
                _initialization_failed_at[model_provider] = time.time()
                return None

        try:
            collection = self._initialize_collection_for_model(model_provider, collection_name)
            if collection:
                _collections[collection_name] = collection
                _initialized[model_provider] = True
                _initialization_failed_at.pop(model_provider, None)  # clear backoff on success
                logger.info(f"Initialized collection {collection_name} for model {model_provider}")
            return collection
        except Exception as e:
            logger.error(f"Failed to initialize collection for {model_provider}: {e}")
            _initialization_failed_at[model_provider] = time.time()
            return None

    def _initialize_db_client(self):
        """Initialize the database client and cache the database object"""
        global _db_client, _db

        if not self.token or not self.endpoint:
            logger.error("Missing AstraDB credentials")
            return False

        try:
            from astrapy import DataAPIClient
            _db_client = DataAPIClient(self.token)
            _db = _db_client.get_database(self.endpoint)  # cache db object
            logger.info("AstraDB DataAPIClient and Database initialized")
            return True
        except Exception as e:
            logger.error(f"Error initializing AstraDB client: {e}")
            return False

    def _initialize_collection_for_model(self, model_provider: str, collection_name: str):
        """Initialize collection for specific model.

        Calls create_collection() directly — astrapy 2.x makes this a no-op when the
        collection already exists with the same settings, so we skip list_collection_names()
        which requires elevated CQL permissions not available on application tokens.
        """
        try:
            from astrapy.info import CollectionDefinition
            from astrapy.constants import VectorMetric

            db = _db  # use cached Database object
            collection_definition = (
                CollectionDefinition.builder()
                .set_vector_dimension(EMBEDDING_DIMENSION)
                .set_vector_metric(VectorMetric.COSINE)
                .build()
            )
            # create_collection is idempotent for same settings — safe to call every time
            collection = db.create_collection(collection_name, definition=collection_definition)
            logger.info(f"Collection {collection_name} ready for {model_provider}")
            return collection
        except Exception as e:
            logger.error(f"Error initializing collection {collection_name}: {e}")
            return None
    
    def add_trading_experience(self, token_address: str, trading_data: Dict[str, Any]) -> str:
        """Add trading experience to model-specific collection"""
        model_provider = trading_data.get('model_provider', 'google' if GOOGLE_API_KEY else 'voyageai')
        collection = self.get_collection_for_model(model_provider)
        
        if not collection:
            logger.warning(f"Collection not available for {model_provider}, skipping experience storage")
            return ""
        
        try:
            # Generate document ID
            doc_id = str(uuid.uuid4())
            timestamp = datetime.now().isoformat()
            
            # Create rich document text for embedding
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
            
            # Get embedding using appropriate provider
            embedding = self.get_embedding(document_text, model_provider, "RETRIEVAL_DOCUMENT")
            
            # Prepare document with rich metadata
            document = {
                "_id": doc_id,
                "document_type": "trading_experience",
                "model_provider": model_provider,  # Track which model created this
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
            
            # Insert document with retry on transient errors
            result = None
            for attempt in range(3):
                try:
                    result = collection.insert_one(document)
                    break
                except Exception as ins_err:
                    if attempt == 2:
                        raise
                    logger.warning(f"AstraDB insert attempt {attempt + 1} failed: {ins_err}, retrying in {1.5 ** attempt:.1f}s")
                    time.sleep(1.5 ** attempt)

            if result and result.inserted_id:
                collection_name = get_collection_name(model_provider)
                logger.info(f"Added trading experience for {token_symbol} to {collection_name}: {doc_id}")
                return doc_id
            else:
                logger.error(f"Failed to insert trading experience: {result}")
                return ""
                
        except Exception as e:
            logger.error(f"Error adding trading experience to vector memory: {e}")
            return ""
    
    def search_similar_experiences(self, query: str, limit: int = 5, filter_criteria: Optional[Dict] = None, model_provider: str = "voyageai") -> List[Dict[str, Any]]:
        """Search for similar trading experiences in model-specific collection"""
        collection = self.get_collection_for_model(model_provider)
        
        if not collection:
            logger.warning(f"Collection not available for {model_provider}, returning empty results")
            return []
        
        try:
            # Get query embedding — use "query" input_type for better semantic search accuracy
            query_embedding = self.get_embedding(query, model_provider, "RETRIEVAL_QUERY", input_type="query")
            
            # Prepare search with vector similarity
            search_kwargs = {
                "sort": {"$vector": query_embedding},
                "limit": limit,
                "include_similarity": True,
                "projection": {"$vector": 0}  # exclude 1024-float embedding from results
            }
            
            # Add filter if provided
            if filter_criteria:
                search_kwargs["filter"] = filter_criteria
            
            # Execute search using correct AstraDB method
            cursor = collection.find(**search_kwargs)
            
            processed_results = []
            for doc in cursor:
                processed_results.append({
                    "id": doc.get("_id"),
                    "similarity": doc.get("$similarity", 0.0),
                    "model_provider": doc.get("model_provider", model_provider),
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
            
            collection_name = get_collection_name(model_provider)
            logger.info(f"Vector search in {collection_name} for '{query}' returned {len(processed_results)} results")
            return processed_results
            
        except Exception as e:
            logger.error(f"Error searching vector memory: {e}")
            return []
    
    def find_similar_tokens(self, token_data: Dict[str, Any], limit: int = 5, model_provider: str = "voyageai") -> List[Dict[str, Any]]:
        """Find similar tokens in model-specific collection"""
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
            
            # Search for similar experiences in same model collection
            results = self.search_similar_experiences(query, limit, model_provider=model_provider)
            
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
                        "model_provider": result["model_provider"],
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

    def get_stats(self, model_provider: str = "voyageai") -> Dict[str, Any]:
        """Get collection statistics for specific model"""
        collection = self.get_collection_for_model(model_provider)
        collection_name = get_collection_name(model_provider)
        
        if not collection:
            return {
                "model_provider": model_provider,
                "collection_name": collection_name,
                "total_records": 0,
                "error": "Collection not available"
            }
        
        try:
            # Count documents using correct AstraDB method
            count = collection.count_documents({}, upper_bound=1000)
            
            # Get statistics
            stats = {
                "model_provider": model_provider,
                "collection_name": collection_name,
                "total_records": count,
                "endpoint": self.endpoint,
                "embedding_dimension": EMBEDDING_DIMENSION,
                "timestamp": datetime.now().isoformat(),
                "status": "healthy"
            }
            
            # Get profitable vs losing trades if we have records
            if count > 0:
                try:
                    profitable_count = collection.count_documents(
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
                "model_provider": model_provider,
                "collection_name": collection_name,
                "total_records": 0,
                "error": str(e)
            }

    def clear_collection(self, model_provider: str = "voyageai") -> bool:
        """Clear documents from model-specific collection"""
        collection = self.get_collection_for_model(model_provider)
        collection_name = get_collection_name(model_provider)
        
        if not collection:
            logger.warning(f"Collection {collection_name} not available, cannot clear")
            return False
        
        try:
            result = collection.delete_many({})
            deleted_count = getattr(result, 'deleted_count', 0)
            logger.info(f"Cleared {deleted_count} documents from {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing collection {collection_name}: {e}")
            return False


# Global instance
astra_store = AstraDBVectorStore()

# ============================================================================
# COMPATIBILITY FUNCTIONS (for existing codebase)
# ============================================================================

def add_to_memory(token_address: str, data: Dict[str, Any]) -> str:
    """Add token information to vector store - compatibility function"""
    return astra_store.add_trading_experience(token_address, data)

def search_memory(query: str, n_results: int = 5, filter_metadata: Optional[Dict] = None, model_provider: str = "voyageai") -> List[Dict[str, Any]]:
    """Search vector memory - compatibility function"""
    return astra_store.search_similar_experiences(query, n_results, filter_metadata, model_provider)

def get_memory_stats(model_provider: str = "voyageai") -> Dict[str, Any]:
    """Get memory statistics - compatibility function"""
    return astra_store.get_stats(model_provider)

def clear_memory(model_provider: str = "voyageai") -> bool:
    """Clear memory - compatibility function"""
    return astra_store.clear_collection(model_provider)

def is_vector_store_available(model_provider: str = "voyageai") -> bool:
    """Check if vector store is available - compatibility function"""
    collection = astra_store.get_collection_for_model(model_provider)
    return collection is not None

def find_similar_tokens(token_data: Dict[str, Any], n_results: int = 5, model_provider: str = "voyageai") -> List[Dict[str, Any]]:
    """Find similar tokens - compatibility function"""
    return astra_store.find_similar_tokens(token_data, n_results, model_provider)

def get_vector_store_info(model_provider: str = "voyageai") -> Dict[str, Any]:
    """Get vector store information - compatibility function"""
    collection_name = get_collection_name(model_provider)
    return {
        "type": "AstraDB",
        "model_provider": model_provider,
        "collection_name": collection_name,
        "available": is_vector_store_available(model_provider),
        "initialized": _initialized.get(model_provider, False),
        "initialization_failed": _initialization_failed.get(model_provider, False),
        "endpoint": ASTRA_DB_API_ENDPOINT,
        "embedding_dimension": EMBEDDING_DIMENSION
    }

# ============================================================================
# NEW AI TRADING SPECIFIC FUNCTIONS
# ============================================================================

def add_trading_experience(token_address: str, trading_data: Dict[str, Any]) -> str:
    """Add trading experience for AI learning"""
    return astra_store.add_trading_experience(token_address, trading_data)

def search_trading_experiences(query: str, model_provider: str, limit: int = 5, filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
    """Search for similar trading experiences - uses global context if model_provider not specified"""
    return astra_store.search_similar_experiences(query, limit, filters, model_provider)

def get_trading_patterns(pattern_type: str = "profitable", model_provider: str = "voyageai") -> List[Dict[str, Any]]:
    """Get trading patterns for AI analysis from model-specific collection"""
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
        
        query = f"Trading patterns for {pattern_type} trades with market analysis"
        results = astra_store.search_similar_experiences(query, limit=20, filter_criteria=filter_criteria, model_provider=model_provider)
        
        return results
        
    except Exception as e:
        logger.error(f"Error getting trading patterns: {e}")
        return []

def learn_from_similar_trades(current_token_data: Dict[str, Any], model_provider: str) -> List[Dict[str, Any]]:
    """Find similar historical trades for AI learning from model-specific collection"""
    return astra_store.find_similar_tokens(current_token_data, 10, model_provider)

# ============================================================================
# CROSS-MODEL COLLABORATION SYSTEM
# ============================================================================

def query_other_model(query: str, current_model: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Allow one model to query the other model's experiences"""
    # Determine the other model
    other_model = "google" if current_model in ["anthropic", "voyageai"] else "voyageai"
    
    logger.info(f"Model {current_model} querying {other_model} with: '{query}'")
    
    try:
        # Search the other model's collection
        results = astra_store.search_similar_experiences(query, limit, model_provider=other_model)
        
        # Add collaboration metadata
        for result in results:
            result["collaboration_info"] = {
                "queried_by": current_model,
                "source_model": other_model,
                "query": query,
                "collaboration_type": "cross_model_query"
            }
        
        logger.info(f"Cross-model query returned {len(results)} results from {other_model}")
        return results
        
    except Exception as e:
        logger.error(f"Error in cross-model query: {e}")
        return []

def get_model_comparison(token_data: Dict[str, Any], claude_limit: int = 3, gemini_limit: int = 3) -> Dict[str, Any]:
    """Get experiences from both models for comparison"""
    try:
        # Create search query based on token characteristics
        query_parts = []
        if token_data.get("symbol"):
            query_parts.append(f"Token similar to {token_data['symbol']}")
        if token_data.get("safety_score", 0) > 0:
            query_parts.append(f"Safety score around {token_data['safety_score']:.0f}")
        if token_data.get("market_cap", 0) > 0:
            query_parts.append(f"Market cap ${token_data['market_cap']:,.0f}")
        
        query = ". ".join(query_parts) if query_parts else "Similar token analysis"
        
        # Get experiences from both models
        claude_experiences = astra_store.search_similar_experiences(query, claude_limit, model_provider="voyageai")
        gemini_experiences = astra_store.search_similar_experiences(query, gemini_limit, model_provider="google")
        
        # Calculate performance metrics for each model
        def calculate_performance(experiences):
            if not experiences:
                return {"total_trades": 0, "win_rate": 0, "avg_profit": 0}
            
            profitable_trades = [exp for exp in experiences if exp["metadata"]["was_profitable"]]
            total_profit = sum(exp["metadata"]["profit_percentage"] for exp in experiences)
            
            return {
                "total_trades": len(experiences),
                "win_rate": len(profitable_trades) / len(experiences) if experiences else 0,
                "avg_profit": total_profit / len(experiences) if experiences else 0,
                "best_profit": max((exp["metadata"]["profit_percentage"] for exp in experiences), default=0),
                "worst_loss": min((exp["metadata"]["profit_percentage"] for exp in experiences), default=0)
            }
        
        claude_performance = calculate_performance(claude_experiences)
        gemini_performance = calculate_performance(gemini_experiences)
        
        return {
            "query": query,
            "token_symbol": token_data.get("symbol", "unknown"),
            "claude_analysis": {
                "model": "claude",
                "experiences": claude_experiences,
                "performance": claude_performance,
                "collection": "claude_trading_memory"
            },
            "gemini_analysis": {
                "model": "gemini", 
                "experiences": gemini_experiences,
                "performance": gemini_performance,
                "collection": "gemini_trading_memory"
            },
            "comparison": {
                "claude_win_rate": claude_performance["win_rate"],
                "gemini_win_rate": gemini_performance["win_rate"],
                "claude_avg_profit": claude_performance["avg_profit"],
                "gemini_avg_profit": gemini_performance["avg_profit"],
                "better_performer": "claude" if claude_performance["win_rate"] > gemini_performance["win_rate"] else "gemini" if gemini_performance["win_rate"] > claude_performance["win_rate"] else "tie"
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in model comparison: {e}")
        return {"error": str(e)}

def share_insight_across_models(insight: Dict[str, Any], source_model: str) -> str:
    """Share a trading insight across both model collections"""
    target_model = "google" if source_model in ["anthropic", "voyageai"] else "voyageai"
    
    try:
        # Create insight document
        insight_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        # Create insight text for embedding
        insight_text = f"""
        Shared Trading Insight from {source_model.upper()}:
        
        Strategy: {insight.get('strategy', 'unknown')}
        Success Rate: {insight.get('success_rate', 0):.1f}%
        Key Pattern: {insight.get('pattern_description', '')}
        
        Market Conditions: {insight.get('market_conditions', '')}
        Token Characteristics: {json.dumps(insight.get('token_characteristics', {}))}
        Risk Factors: {json.dumps(insight.get('risk_factors', []))}
        Success Factors: {json.dumps(insight.get('success_factors', []))}
        
        Insight Details: {insight.get('detailed_analysis', '')}
        Recommended Actions: {insight.get('recommendations', '')}
        
        Shared Knowledge: This insight has been shared across AI models for collaborative learning.
        """
        
        # Get embedding for target model
        embedding = astra_store.get_embedding(insight_text, target_model, "RETRIEVAL_DOCUMENT")
        
        # Create shared insight document
        shared_document = {
            "_id": insight_id,
            "document_type": "shared_insight",
            "source_model": source_model,
            "target_model": target_model,
            "model_provider": target_model,  # Store in target model's collection
            "timestamp": timestamp,
            
            # Insight metadata
            "strategy": insight.get("strategy", "unknown"),
            "success_rate": insight.get("success_rate", 0),
            "pattern_type": insight.get("pattern_type", "general"),
            "confidence_score": insight.get("confidence_score", 0),
            
            # Content
            "document_text": insight_text,
            "original_insight": insight,
            "collaboration_type": "shared_insight",
            
            # Vector embedding
            "$vector": embedding
        }
        
        # Store in target model's collection
        target_collection = astra_store.get_collection_for_model(target_model)
        if target_collection:
            result = target_collection.insert_one(shared_document)
            if result and result.inserted_id:
                logger.info(f"Shared insight from {source_model} to {target_model}: {insight_id}")
                return insight_id
            else:
                logger.error(f"Failed to share insight: {result}")
                return ""
        else:
            logger.error(f"Target collection for {target_model} not available")
            return ""
            
    except Exception as e:
        logger.error(f"Error sharing insight across models: {e}")
        return ""

def get_collaborative_analysis(token_data: Dict[str, Any], current_model: str) -> Dict[str, Any]:
    """Get collaborative analysis combining both models' perspectives"""
    try:
        # Get current model's analysis
        current_experiences = astra_store.find_similar_tokens(token_data, 5, current_model)
        
        # Query the other model for its perspective
        other_model = "google" if current_model in ["anthropic", "voyageai"] else "voyageai"
        query = f"Token analysis for {token_data.get('symbol', 'unknown')} with safety score {token_data.get('safety_score', 0)}"
        other_experiences = query_other_model(query, current_model, 5)
        
        # Analyze shared insights from the other model
        shared_insights_query = f"shared insights about {token_data.get('symbol', 'similar tokens')}"
        shared_insights = astra_store.search_similar_experiences(
            shared_insights_query, 3, 
            filter_criteria={"document_type": "shared_insight"}, 
            model_provider=current_model
        )
        
        # Compile collaborative analysis
        analysis = {
            "token_symbol": token_data.get("symbol", "unknown"),
            "analysis_timestamp": datetime.now().isoformat(),
            "current_model": current_model,
            "other_model": other_model,
            
            # Current model analysis
            "own_analysis": {
                "model": current_model,
                "similar_tokens": len(current_experiences),
                "experiences": current_experiences[:3],  # Top 3 for brevity
                "collection_source": get_collection_name(current_model)
            },
            
            # Other model analysis
            "collaborative_analysis": {
                "model": other_model,
                "cross_model_experiences": len(other_experiences),
                "experiences": other_experiences[:3],  # Top 3 for brevity
                "collection_source": get_collection_name(other_model)
            },
            
            # Shared insights
            "shared_insights": {
                "available_insights": len(shared_insights),
                "insights": shared_insights
            },
            
            # Combined recommendations
            "combined_perspective": {
                "total_experiences_analyzed": len(current_experiences) + len(other_experiences),
                "models_consulted": [current_model, other_model],
                "collaboration_type": "full_cross_model_analysis"
            }
        }
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error in collaborative analysis: {e}")
        return {"error": str(e)}

# ============================================================================
# MODEL PROVIDER CONTEXT SYSTEM
# ============================================================================

def set_current_model_provider(provider: str):
    """Set the current model provider for global context"""
    global _current_model_provider
    _current_model_provider = provider
    logger.info(f"Set current model provider to: {provider}")

def get_current_model_provider() -> str:
    """Get the current model provider from global context"""
    return _current_model_provider