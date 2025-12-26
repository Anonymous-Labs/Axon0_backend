# AXON - Universal Memory Layer

A comprehensive memory system for AI agents and intelligent applications, built with FastAPI and React.

## 🧠 Overview

AXON provides a universal memory layer that enables AI agents and chatbots to remember, learn, and adapt over time. It features semantic search, intelligent compression, clustering, and seamless integration with popular AI frameworks.

## 🚀 Features

### Core Memory Features
- **Semantic Memory Search**: Natural language queries with vector similarity
- **Intelligent Compression**: Automatic summarization of old memories
- **Episodic Clustering**: Group related memories for better organization
- **Real-time WebSocket Support**: Live memory updates and retrieval
- **API Key Management**: Create and manage API keys for programmatic access
- **Rate Limiting**: Built-in rate limiting (60 req/min IP, 100 req/min API key)
- **Comprehensive Dashboard**: Manage memories, search, API keys, and settings
- **Multi-framework Integration**: Works with LangChain, CrewAI, Agno, and more
- **Secure Authentication**: JWT-based auth with proper password hashing
- **Scalable Architecture**: Built for high-performance and multi-tenancy

### 🧠 Enhanced Memory System (Latest Update)

#### Vector Database Integration
- **FAISS Integration**: High-performance vector similarity search
- **Sentence Transformers**: State-of-the-art embedding generation using `all-MiniLM-L6-v2`
- **Automatic Embedding**: All memories are automatically vectorized on creation
- **Efficient Retrieval**: Sub-linear time complexity for similarity searches

#### AI-Powered Content Processing
- **Google Gemini Integration**: Advanced content restructuring and chunking
- **Intelligent Chunking**: Content broken into meaningful, self-contained chunks
- **Context Preservation**: Maintains temporal and causal relationships
- **Metadata Extraction**: Automatic extraction of key concepts, topics, and importance

#### Episodic Memory & Clustering
- **Episodic Clusters**: Group related memories by time, context, or topic
- **Decision Trails**: Track decision-making processes across memories
- **Project-Level Recall**: Understand "what happened last time we built X"
- **Temporal Linking**: Connect memories across time periods

#### Context Composer
- **Smart Ranking**: Ranks memories based on usage patterns, tags, and relevance
- **Multi-Factor Scoring**: Combines semantic similarity, recency, importance, and feedback
- **Contextual Restructuring**: Reorganizes memories for specific purposes (learning, decision-making)
- **Dynamic Composition**: Creates coherent responses from multiple memory sources

#### Feedback Loop System
- **Continuous Learning**: System improves based on user feedback
- **Missing Context Detection**: Automatically identifies and fills contextual gaps
- **Relevance Optimization**: Adjusts memory importance and relationships based on usage
- **Quality Metrics**: Tracks and improves memory retrieval quality over time

#### Memory Relationships & Graphs
- **Semantic Relationships**: Connects memories by meaning and context
- **Network Analysis**: Uses graph theory for memory organization
- **Community Detection**: Identifies natural clusters and themes
- **Centrality Scoring**: Highlights most important memories in networks

### 🎯 Episodic Clustering Benefits

The episodic clustering system unlocks several key capabilities:

1. **Project-Level Recall**: Remember entire project contexts and decision processes
2. **Decision Trails**: Track how decisions were made and what led to them
3. **Knowledge Evolution**: See how understanding developed over time
4. **Context Preservation**: Maintain situational awareness across sessions
5. **Pattern Recognition**: Identify recurring themes and approaches

### 🔄 Memory Processing Pipeline

When a memory is created, it goes through this comprehensive pipeline:

1. **Content Analysis** → Gemini AI analyzes and restructures content
2. **Chunking** → Content broken into meaningful chunks with embeddings
3. **Vector Storage** → Embeddings stored in FAISS for fast retrieval
4. **Relationship Discovery** → Similar memories and relationships identified
5. **Clustering** → Added to appropriate episodic clusters
6. **Metadata Enrichment** → Tags, concepts, and importance scores added
7. **Feedback Integration** → System learns from user interactions

### 🎨 Frontend Visualizations

- **Cluster View**: Visual clusters with importance indicators and key concepts
- **Graph View**: Network visualization of memory relationships
- **Timeline View**: Chronological view of episodic clusters and decision trails
- **Interactive Exploration**: Click to navigate between related memories

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI       │    │   WebSocket     │    │   React UI      │
│   REST API      │    │   Gateway       │    │   Dashboard     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Memory       │
                    │   Core Engine  │
                    └─────────────────┘
                             │
                    ┌─────────────────┐
                    │   SQLite /      │
                    │   Vector DB     │
                    └─────────────────┘
```

## 📦 Installation

### Backend Setup

1. **Navigate to backend directory:**
   ```bash
   cd Axon0_backend
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

   **Note**: The enhanced memory system requires additional packages:
   - `faiss-cpu` for vector similarity search
   - `google-generativeai` for AI-powered content processing
   - `sentence-transformers` for embedding generation
   - `networkx` for graph analysis
   - `nltk` and `spacy` for text processing

4. **Set up Gemini API Key:**
   Create a `.env` file in the backend directory:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

4. **Set up environment variables:**
   ```bash
   cp .env.template .env
   # Edit .env with your configuration
   ```

5. **Run the server:**
   ```bash
   python run.py
   ```

The API will be available at `http://localhost:8000`

### Frontend Setup

1. **Navigate to frontend directory:**
   ```bash
   cd Axon0_Frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Start development server:**
   ```bash
   npm run dev
   ```

The frontend will be available at `http://localhost:3000`

### Dashboard Features
- **Memory Management**: Add, view, search, and organize memories
- **API Key Management**: Create, configure, and manage API keys
- **Search Interface**: Advanced search with filters and semantic matching
- **Settings**: User preferences and account management
- **Documentation**: Built-in API documentation with framework examples

## 🔑 Authentication

AXON supports two authentication methods:

### JWT Authentication (Web Dashboard)
For web dashboard access, use JWT-based authentication:

```bash
# Register
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "securepassword123"
  }'

# Login
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=securepassword123"
```

### API Key Authentication (Programmatic Access)
For API access, create and use API keys through the dashboard:

```bash
# Create API key via dashboard, then use:
curl -X GET "http://localhost:8000/api/v1/memories/" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

## 📚 API Documentation

### Memory Operations

#### Create Memory
```bash
curl -X POST "http://localhost:8000/api/v1/memories/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "This is a test memory about machine learning",
    "title": "ML Concepts",
    "importance_score": 0.8,
    "tags": ["AI", "machine-learning"],
    "metadata": {"category": "technical"}
  }'
```

#### Search Memories
```bash
curl -X POST "http://localhost:8000/api/v1/memories/search" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning concepts",
    "limit": 10,
    "tags": ["AI"]
  }'
```

#### Get Memory Stats
```bash
curl "http://localhost:8000/api/v1/memories/stats/overview" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## 🔗 Framework Integration

### LangChain Integration

```python
from langchain.memory import ConversationBufferMemory
from langchain.llms import OpenAI
import requests

class AxonMemory(ConversationBufferMemory):
    def __init__(self, api_url="http://localhost:8000", api_key=None):
        super().__init__()
        self.api_url = api_url
        self.api_key = api_key
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def save_context(self, inputs, outputs):
        # Save conversation to AXON
        memory_data = {
            "content": f"Input: {inputs['input']}\nOutput: {outputs['output']}",
            "importance_score": 0.7,
            "tags": ["conversation", "langchain"]
        }

        requests.post(
            f"{self.api_url}/api/v1/memories/",
            json=memory_data,
            headers=self.headers
        )

        super().save_context(inputs, outputs)

    def search_memories(self, query, limit=5):
        response = requests.post(
            f"{self.api_url}/api/v1/memories/search",
            json={"query": query, "limit": limit},
            headers=self.headers
        )
        return response.json()

# Usage
memory = AxonMemory(api_key="your-jwt-token")
llm = OpenAI(temperature=0.7)
conversation = ConversationChain(llm=llm, memory=memory)
```

### CrewAI Integration

```python
from crewai import Agent, Task, Crew
from crewai.memory import AxonMemory
import requests

class CrewAIAxonMemory:
    def __init__(self, api_url="http://localhost:8000", api_key=None):
        self.api_url = api_url
        self.api_key = api_key
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def store(self, content, metadata=None):
        """Store memory in AXON"""
        memory_data = {
            "content": content,
            "importance_score": metadata.get("importance", 0.5) if metadata else 0.5,
            "tags": metadata.get("tags", []) if metadata else [],
            "metadata": metadata or {}
        }

        response = requests.post(
            f"{self.api_url}/api/v1/memories/",
            json=memory_data,
            headers=self.headers
        )
        return response.json()

    def retrieve(self, query, limit=10):
        """Retrieve relevant memories"""
        response = requests.post(
            f"{self.api_url}/api/v1/memories/search",
            json={"query": query, "limit": limit},
            headers=self.headers
        )
        return response.json()

    def get_context(self, task_description):
        """Get relevant context for a task"""
        memories = self.retrieve(task_description, limit=5)
        context = "\n".join([m["content"] for m in memories.get("memories", [])])
        return context

# Usage
memory_system = CrewAIAxonMemory(api_key="your-jwt-token")

# Create agent with AXON memory
agent = Agent(
    role="Research Assistant",
    goal="Conduct thorough research on given topics",
    backstory="You are an expert researcher with access to a comprehensive memory system",
    memory=memory_system
)

# Create task
task = Task(
    description="Research the latest developments in quantum computing",
    agent=agent,
    context_callback=lambda: memory_system.get_context("quantum computing research")
)

crew = Crew(agents=[agent], tasks=[task])
result = crew.kickoff()
```

### Agno Integration

```python
from agno.agent import Agent
from agno.memory import Memory
import requests

class AgnoAxonMemory(Memory):
    def __init__(self, api_url="http://localhost:8000", api_key=None):
        self.api_url = api_url
        self.api_key = api_key
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def add(self, content, metadata=None):
        """Add memory to AXON"""
        memory_data = {
            "content": content,
            "importance_score": metadata.get("importance", 0.5) if metadata else 0.5,
            "tags": metadata.get("tags", []) if metadata else [],
            "metadata": metadata or {}
        }

        response = requests.post(
            f"{self.api_url}/api/v1/memories/",
            json=memory_data,
            headers=self.headers
        )
        return response.json()

    def search(self, query, limit=10):
        """Search memories in AXON"""
        response = requests.post(
            f"{self.api_url}/api/v1/memories/search",
            json={"query": query, "limit": limit},
            headers=self.headers
        )
        return [m["content"] for m in response.json().get("memories", [])]

    def get_all(self):
        """Get all memories"""
        response = requests.get(
            f"{self.api_url}/api/v1/memories/",
            headers=self.headers
        )
        return [m["content"] for m in response.json()]

# Usage
memory = AgnoAxonMemory(api_key="your-jwt-token")

agent = Agent(
    name="Research Agent",
    memory=memory,
    instructions="You are a research agent with persistent memory capabilities"
)

# The agent will automatically use AXON for memory management
response = agent.run("What are the benefits of renewable energy?")
```

### Simple Python Integration

```python
import requests

class AxonClient:
    def __init__(self, api_url="http://localhost:8000", api_key=None):
        self.api_url = api_url
        self.api_key = api_key
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def store_memory(self, content, title=None, tags=None, importance=0.5):
        """Store a memory"""
        data = {
            "content": content,
            "importance_score": importance
        }
        if title:
            data["title"] = title
        if tags:
            data["tags"] = tags

        response = requests.post(
            f"{self.api_url}/api/v1/memories/",
            json=data,
            headers=self.headers
        )
        return response.json()

    def search_memories(self, query, limit=10):
        """Search memories"""
        response = requests.post(
            f"{self.api_url}/api/v1/memories/search",
            json={"query": query, "limit": limit},
            headers=self.headers
        )
        return response.json()

    def get_stats(self):
        """Get memory statistics"""
        response = requests.get(
            f"{self.api_url}/api/v1/memories/stats/overview",
            headers=self.headers
        )
        return response.json()

# Usage
client = AxonClient(api_key="your-jwt-token")

# Store a memory
client.store_memory(
    content="Machine learning is a subset of artificial intelligence",
    title="ML Definition",
    tags=["AI", "machine-learning"],
    importance=0.9
)

# Search memories
results = client.search_memories("artificial intelligence")
print(results)

# Get stats
stats = client.get_stats()
print(f"Total memories: {stats['total_memories']}")
```

## 🔧 Configuration

### Environment Variables

```bash
# Application
APP_NAME=Axon Memory System
DEBUG=True
SECRET_KEY=your-super-secret-key

# Database
DATABASE_URL=sqlite:///./axon.db

# JWT
JWT_SECRET_KEY=your-jwt-secret
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Gemini API (for summarization)
GEMINI_API_KEY=your-gemini-api-key

# Redis (for workers)
REDIS_URL=redis://localhost:6379

# Server
HOST=0.0.0.0
PORT=8000
```

## 🛡️ Rate Limiting

AXON implements rate limiting to ensure fair usage:

- **IP-based limiting**: 60 requests per minute per IP address
- **API key limiting**: 100 requests per minute per API key
- **Rate limit headers**: Check `X-RateLimit-*` headers in responses
- **Retry-After**: When rate limited, wait for the time specified in `Retry-After` header

## 🧪 Testing

Run the test suite:

```bash
# Backend tests
cd Axon0_backend
pytest

# Frontend tests (when implemented)
cd Axon0_Frontend
npm test
```

## 📄 API Reference

### Authentication Endpoints

- `POST /auth/register` - Register new user
- `POST /auth/login` - Login user
- `GET /auth/me` - Get current user info

### Memory Endpoints

- `GET /api/v1/memories/` - List user memories
- `POST /api/v1/memories/` - Create memory
- `GET /api/v1/memories/{id}` - Get specific memory
- `PUT /api/v1/memories/{id}` - Update memory
- `DELETE /api/v1/memories/{id}` - Delete memory
- `POST /api/v1/memories/search` - Search memories
- `GET /api/v1/memories/stats/overview` - Get memory statistics

### API Key Endpoints

- `GET /api/v1/api-keys/` - List user's API keys
- `POST /api/v1/api-keys/` - Create new API key
- `DELETE /api/v1/api-keys/{id}` - Delete API key
- `PUT /api/v1/api-keys/{id}/regenerate` - Regenerate API key

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.

## 🆘 Support

For support and questions:
- Open an issue on GitHub
- Check the documentation
- Join our Discord community

---

Built with ❤️ for the AI community