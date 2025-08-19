# LLM Result Retrieval and Scoring Systems Research

## 1. GPTCache - Semantic Cache for LLMs

**Repository**: https://github.com/zilliztech/GPTCache
**Stars**: 7.7k
**License**: MIT

### Key Features:
- Semantic caching for LLM responses using vector similarity search
- Modular architecture with customizable components
- Support for exact and similar matching with configurable similarity thresholds
- Integration with LangChain and llama_index

### Architecture Components:
1. **Adapter**: User interface to adapt different LLM model requests to GPTCache protocol
2. **Pre-processor**: Extracts key information from requests and preprocesses
3. **Context Buffer**: Maintains session context
4. **Encoder**: Embeds text into dense vectors for similarity search
5. **Cache Manager**: Handles searching, saving, and evicting data
6. **Ranker**: Evaluates similarity by judging quality of cached answers
7. **Post-processor**: Determines which cached answers to return to user

### Similarity Evaluation:
- Uses vector embeddings (ONNX, OpenAI, etc.) for semantic similarity
- Supports multiple vector databases (Faiss, Milvus, Weaviate, etc.)
- Configurable similarity thresholds
- Distance-based evaluation (SearchDistanceEvaluation)
- Top-k similar search results

### Success Scoring:
- Temperature-based post-processing for result selection
- Similarity scores from vector database queries
- Configurable similarity thresholds for cache hits
- Support for custom evaluation functions

### Implementation Example:
```python
from gptcache import cache
from gptcache.embedding import Onnx
from gptcache.manager import CacheBase, VectorBase, get_data_manager
from gptcache.similarity_evaluation.distance import SearchDistanceEvaluation

onnx = Onnx()
data_manager = get_data_manager(CacheBase("sqlite"), VectorBase("faiss", dimension=onnx.dimension))
cache.init(
    embedding_func=onnx.to_embeddings,
    data_manager=data_manager,
    similarity_evaluation=SearchDistanceEvaluation(),
)
```




## 2. Case-Based Reasoning (CBR) for LLM Agents

**Paper**: "Review of Case-Based Reasoning for LLM Agents: Theoretical Foundations, Architectural Components, and Cognitive Integration"
**URL**: https://arxiv.org/html/2504.06943v2
**Authors**: Kostas Hatalis, Despina Christou, Vyshnavi Kondapalli

### Overview:
CBR-enhanced LLM agents solve new problems by referencing past experiences and solutions. This approach addresses common LLM limitations like hallucinations and lack of contextual memory across interactions.

### Core CBR Process (4 Steps):
1. **Retrieve** relevant cases
2. **Reuse** the knowledge embedded in these cases
3. **Revise** the proposed solution
4. **Retain** the new problem-solution pair for future reference

### Architectural Components:

#### 4.1 Case Representation and Indexing
- **Multi-faceted representation scheme** capturing semantic richness
- **Dense semantic embeddings** (E_i) from foundation LLM
- **Sparse feature-based indices** (I_i) for domain-specific attributes
- **Hierarchical organization** for efficient retrieval

#### 4.2 Hybrid Retrieval Mechanisms
Mathematical formulation for retrieving relevant cases:
```
R(q, L) = λ₁ · R_semantic(q, L) ∪ λ₂ · R_feature(q, L) ∪ λ₃ · R_structural(q, L)
```

Where:
- **R_semantic**: Retrieval based on embedding similarity in LLM's latent space
- **R_feature**: Search based on explicit feature matching
- **R_structural**: Identifies cases with similar problem structures or solution patterns
- **λ₁, λ₂, λ₃**: Weighting coefficients for each retrieval mechanism

#### 4.3 Adaptation Mechanisms
Three sophisticated adaptation approaches:

1. **Transformational Adaptation**: Modifies retrieved solutions through substitution, deletion, or insertion operations
2. **Compositional Adaptation**: Integrates components from multiple retrieved solutions
3. **Generative Adaptation**: Leverages LLM's generative capabilities to synthesize novel solutions

#### 4.4 Integration with LLM Reasoning
Weighted combination of reasoning pathways:
```
f_reasoning(q) = ω₁ · f_CBR(q) + ω₂ · f_CoT(q) + ω₃ · f_parametric(q)
```

Where:
- **f_CBR**: Case-based reasoning pathway
- **f_CoT**: Chain-of-thought reasoning process
- **f_parametric**: Direct inference from model's parametric knowledge
- **ω₁, ω₂, ω₃**: Dynamic weights determined by confidence metrics

### Key Benefits:
- **Enhanced reasoning transparency** through explicit case references
- **Improved domain adaptation** by leveraging relevant past experiences
- **Better solution quality** through experience-based learning
- **Reduced hallucinations** by grounding responses in verified past solutions
- **Continuous learning** from new problem-solution pairs

### Cognitive Dimensions:
- **Self-reflection**: Agents can evaluate their own reasoning processes
- **Introspection**: Understanding of internal knowledge and reasoning
- **Curiosity**: Drive to explore and learn from new experiences
- **Goal-driven autonomy**: Dynamic goal selection and management

### Implementation Considerations:
- Requires vector database (like ChromaDB) for efficient similarity search
- Need for structured case representation with metadata
- Success scoring mechanisms for solution quality assessment
- Continuous case base maintenance and optimization


## 3. Mem0 - Universal Memory Layer for AI Agents

**Repository**: https://github.com/mem0ai/mem0
**Stars**: 38.4k
**License**: Apache 2.0

### Overview:
Mem0 enhances AI assistants and agents with an intelligent memory layer, enabling personalized AI interactions. It remembers user preferences, adapts to individual needs, and continuously learns over time.

### Performance Metrics:
- **+26% Accuracy** over OpenAI Memory on the LOCOMO benchmark
- **91% Faster Responses** than full-context approaches
- **90% Lower Token Usage** than full-context methods

### Key Features:
- **Multi-Level Memory**: User, Session, and Agent state retention
- **Developer-Friendly**: Intuitive API with cross-platform SDKs
- **Semantic Search**: Efficient retrieval of relevant memories
- **Continuous Learning**: Automatic memory creation from conversations

### Architecture:
```python
from mem0 import Memory

memory = Memory()

# Retrieve relevant memories
relevant_memories = memory.search(query=message, user_id=user_id, limit=3)

# Add new memories from conversation
memory.add(messages, user_id=user_id)
```

### Use Cases:
- AI Assistants with consistent, context-rich conversations
- Customer Support with past ticket and user history recall
- Healthcare with patient preference and history tracking
- Productivity and Gaming with adaptive workflows

## 4. AgentVectorDB (AVDB) - Cognitive Core for AI Agents

**Repository**: https://github.com/superagenticAI/agentvectordb
**Stars**: 6 (newer project)
**License**: Apache 2.0

### Overview:
Specialized memory management system built on LanceDB, providing optimized cognitive architecture for AI agents with agent-specific memory patterns and importance scoring.

### Key Features:
- **Persistent Storage**: File-based, no server required
- **Semantic Search**: Efficient ANN search with filtering
- **Agent-Optimized**: Purpose-built for AI systems
- **Memory Lifecycle**: Complete CRUD operations
- **Smart Pruning**: Intelligent memory management
- **Importance Scoring**: Weighted memory relevance

### Architecture:
```python
from agentvectordb import AgentVectorDBStore
from agentvectordb.embeddings import DefaultTextEmbeddingFunction

store = AgentVectorDBStore(db_path="./agent_db")
ef = DefaultTextEmbeddingFunction(dimension=384)

memories = store.get_or_create_collection(
    name="agent_memories",
    embedding_function=ef
)

# Add memories with importance scoring
memories.add_batch([{
    "content": "User prefers dark mode",
    "type": "preference", 
    "importance_score": 0.8
}])

# Query with filtering
results = memories.query(
    query_text="user preferences",
    filter_sql="importance_score > 0.5",
    k=2
)
```

### Memory Types Supported:
- Episodic memories
- Semantic knowledge
- Procedural information
- Short-term observations
- Long-term knowledge

## 5. OPRO (Optimization by Prompting)

**Repository**: https://github.com/google-deepmind/opro
**Stars**: 597
**License**: Apache 2.0
**Paper**: https://arxiv.org/abs/2309.03409

### Overview:
OPRO leverages LLMs as optimizers, using natural language descriptions of optimization problems and iteratively generating new solutions based on previous results and their scores.

### Key Approach:
1. **Problem Description**: Describe optimization problem in natural language
2. **Solution Generation**: LLM generates candidate solutions
3. **Evaluation**: Score solutions using evaluation metrics
4. **Iterative Improvement**: Use previous results and scores to generate better solutions

### Implementation:
```python
# Optimization loop
for step in range(optimization_steps):
    # Generate new instructions based on previous results
    new_instructions = optimizer_llm.generate(
        prompt=optimization_prompt + previous_results_with_scores
    )
    
    # Evaluate new instructions
    scores = evaluate_instructions(new_instructions, test_data)
    
    # Update history with results and scores
    previous_results_with_scores.append((new_instructions, scores))
```

### Success Scoring:
- Task-specific evaluation metrics (accuracy, performance, etc.)
- Comparative scoring against previous solutions
- Meta-optimization of scoring functions themselves

## 6. Additional Relevant Systems

### DeepEval - LLM Evaluation Framework
**Repository**: https://github.com/confident-ai/deepeval
- Comprehensive LLM evaluation metrics
- Automated scoring systems
- Integration with various LLM providers

### LM Evaluation Harness
**Repository**: https://github.com/EleutherAI/lm-evaluation-harness
- Unified framework for testing generative language models
- Large number of evaluation tasks
- Standardized benchmarking

### OpenAI Evals
**Repository**: https://github.com/openai/evals
- Framework for evaluating LLMs and systems built using LLMs
- Registry of existing evaluations
- Custom evaluation creation tools

