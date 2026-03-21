

import pytest
import uuid
import pytest
import uuid
import pytest
import uuid
from unittest.mock import MagicMock, patch, ANY
from src.memory.astra_vector_store import AstraDBVectorStore, EMBEDDING_DIMENSION

@pytest.fixture
def mock_astra_client():
    """Fixture to mock the astrapy DataAPIClient."""
    with patch('astrapy.DataAPIClient') as mock_client_class:
        mock_db = MagicMock()
        mock_collection = MagicMock()
        
        mock_client_instance = MagicMock()
        mock_client_instance.get_database.return_value = mock_db
        mock_db.get_collection.return_value = mock_collection
        mock_db.list_collection_names.return_value = ["claude_trading_memory", "gemini_trading_memory"]
        
        mock_client_class.return_value = mock_client_instance
        
        yield {
            "client_class": mock_client_class,
            "client_instance": mock_client_instance,
            "db": mock_db,
            "collection": mock_collection
        }

@pytest.fixture
def mock_embedding_clients():
    """Fixture to mock all embedding generation clients."""
    with patch('src.memory.astra_vector_store.GoogleGenerativeAIEmbeddings') as mock_gemini, \
         patch('voyageai.Client') as mock_voyage, \
         patch('openai.OpenAI') as mock_openai:
        
        # Configure Gemini mock
        mock_gemini_instance = MagicMock()
        mock_gemini_instance.embed_query.return_value = [0.1] * EMBEDDING_DIMENSION
        mock_gemini.return_value = mock_gemini_instance

        # Configure VoyageAI mock
        mock_voyage_instance = MagicMock()
        mock_voyage_instance.embed.return_value = MagicMock(embeddings=[[0.2] * EMBEDDING_DIMENSION])
        mock_voyage.return_value = mock_voyage_instance

        # Configure OpenAI mock
        mock_openai_instance = MagicMock()
        mock_openai_instance.embeddings.create.return_value = MagicMock(data=[MagicMock(embedding=[0.3] * EMBEDDING_DIMENSION)])
        mock_openai.return_value = mock_openai_instance

        yield {
            "gemini": mock_gemini,
            "voyage": mock_voyage,
            "openai": mock_openai
        }

@pytest.fixture
def astra_store(mock_astra_client, mock_embedding_clients):
    """Returns an instance of the AstraDBVectorStore with mocked dependencies."""
    with patch.dict('os.environ', {
        'ASTRA_DB_APPLICATION_TOKEN': 'test-token',
        'ASTRA_DB_API_ENDPOINT': 'test-endpoint',
        'GOOGLE_API_KEY': 'test-google-key',
        'VOYAGEAI_API_KEY': 'test-voyage-key',
        'OPENAI_API_KEY': 'test-openai-key'
    }):
        store = AstraDBVectorStore()
        # Manually set the client to our mock since __init__ is complex
        store.client = mock_astra_client["client_instance"]
    return store

def test_get_embedding_selects_correct_provider(astra_store, mock_embedding_clients):
    """Tests that the correct embedding provider is chosen based on the model_provider."""
    # Test Gemini
    astra_store.get_embedding("test", model_provider="google")
    mock_embedding_clients["gemini"].assert_called()

    # Test VoyageAI (for anthropic/claude)
    astra_store.get_embedding("test", model_provider="anthropic")
    mock_embedding_clients["voyage"].assert_called()

    # Test fallback to VoyageAI
    with patch.dict('os.environ', {'GOOGLE_API_KEY': ''}):
        astra_store.get_embedding("test", model_provider="google")
        mock_embedding_clients["voyage"].assert_called()

def test_add_trading_experience(astra_store, mock_astra_client):
    """Tests the addition of a trading experience document to the correct collection."""
    mock_collection = mock_astra_client["collection"]
    mock_collection.insert_one.return_value = MagicMock(inserted_id=uuid.uuid4())

    trading_data = {
        "token_symbol": "TEST",
        "trade_type": "buy",
        "profit_percentage": 10.0,
        "ai_reasoning": "Test reasoning",
        "model_provider": "google" # Specify model to test collection selection
    }
    
    doc_id = astra_store.add_trading_experience("TestTokenAddress", trading_data)

    import uuid

    assert isinstance(doc_id, uuid.UUID)
    mock_collection.insert_one.assert_called_once()
    # Check that the document has the correct structure
    inserted_doc = mock_collection.insert_one.call_args[0][0]
    assert inserted_doc["model_provider"] == "google"
    assert "$vector" in inserted_doc and len(inserted_doc["$vector"]) == EMBEDDING_DIMENSION

def test_search_similar_experiences(astra_store, mock_astra_client):
    """Tests the vector search functionality."""
    mock_collection = mock_astra_client["collection"]
    mock_collection.find.return_value = iter([
            {"_id": "doc1", "$similarity": 0.9, "ai_reasoning": "Reasoning 1"},
            {"_id": "doc2", "$similarity": 0.8, "ai_reasoning": "Reasoning 2"}
        ])

    results = astra_store.search_similar_experiences("test query", model_provider="google")

    assert len(results) == 2
    assert results[0]["id"] == "doc1"
    assert results[0]["similarity"] == 0.9
    mock_collection.find.assert_called_once()

def test_get_collection_for_model_creation(astra_store, mock_astra_client):
    """Tests that a new collection is created if it doesn't exist."""
    mock_db = mock_astra_client["db"]
    mock_db.list_collection_names.return_value = [] # Simulate no existing collections

    # Force re-initialization for the test
    astra_store._collections = {}
    astra_store._initialized = {}
    astra_store.client = None # Force client re-initialization
    
    astra_store.get_collection_for_model("google")

    mock_db.create_collection.assert_called_once_with(
        "gemini_trading_memory",
        definition=ANY
    )

