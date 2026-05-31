# JUNO AI - AI/ML Avancado

## Arquitetura de IA

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚    RAG      â”‚  â”‚ Fine-tuning â”‚  â”‚   Agents    â”‚  â”‚ Predictions â”‚
â”‚  Pipeline   â”‚  â”‚   (LoRA)    â”‚  â”‚  (LangChain)â”‚  â”‚  (ML Ops)   â”‚
â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”˜
       â”‚                â”‚                â”‚                â”‚
       â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                        â”‚
              â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
              â”‚   ChromaDB        â”‚
              â”‚   Vector Store    â”‚
              â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

## RAG Pipeline

- **Chunking**: RecursiveCharacterTextSplitter (512 tokens, 50 overlap)
- **Embeddings**: sentence-transformers/all-MiniLM-L6-v2
- **Vector DB**: ChromaDB com persistencia DuckDB+Parquet
- **Retrieval**: Hybrid search (semantic + keyword) com pesos ajustaveis
- **API**: /ai/rag/index, /ai/rag/query, /ai/rag/stats

## Fine-tuning

- **Tecnica**: LoRA/QLoRA (4-bit quantization)
- **Modelo base**: microsoft/DialoGPT-medium (configuravel)
- **Hiperparametros**: r=16, alpha=32, dropout=0.05
- **Dataset**: Formato instruction/input/output
- **API**: /ai/finetuning/train, /ai/finetuning/generate

## Agentes Autonomos

- **Orchestrator**: MultiAgentOrchestrator com task queue
- **Tools**: Registry dinamico com search_knowledge, calculate, get_time
- **Memoria**: Contexto por agente (ultimos 100 mensagens)
- **API**: /ai/agents/tasks, /ai/agents/workflow, /ai/agents/tools

## Real-time Predictions

- **Feature Store**: Redis-based com TTL (online: 1h, offline: 7d)
- **Model Registry**: Versionamento com sklearn/pytorch/onnx support
- **A/B Testing**: Deterministic assignment, metric tracking, result analysis
- **API**: /ai/predictions/predict, /ai/predictions/abtest

## Variaveis de Ambiente

Ver `.env.example` para todas as variaveis necessarias.
