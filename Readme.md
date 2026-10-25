# 🤖 Saathi AI

### 📚 AI-Powered Document Intelligence Platform

Saathi AI helps users upload documents and ask questions about their content. It uses Retrieval-Augmented Generation (RAG) to retrieve relevant information from documents and generate answers with supporting source information.

## ✨ Features

- 📄 **Document Upload and Processing** — Extracts text from uploaded PDF documents.
- 🧩 **Intelligent Chunking** — Splits extracted text into manageable chunks and associates metadata.
- 🔎 **Hybrid Retrieval** — Combines semantic vector retrieval with keyword-based search.
- 💬 **Context-Aware Chat** — Uses relevant document content and conversation history to support responses.
- 📚 **Multi-Document Chat** — Supports asking questions across selected documents.
- 🔐 **Authentication** — Provides authentication-related API routes and request validation.
- ☁️ **Cloud Document Storage** — Stores original PDFs in Supabase Storage.
- 🧠 **Vector Search** — Uses Qdrant to store and retrieve document chunks and their embeddings.
- 🧾 **Source Information** — Returns source metadata with answers.
- 🧪 **Retrieval Evaluation** — Includes tests and evaluation utilities for retrieval behavior.

## 🏗️ Architecture

### RAG Question-Answering Flow

                         ┌───────────────────────────────┐
                         │         Web Frontend          │
                         │      HTML / CSS / JavaScript  │
                         │ Login • Documents • Chat UI   │
                         └───────────────┬───────────────┘
                                         │
                              HTTP JSON + Bearer token
                                         │
                                         ▼
                         ┌───────────────────────────────┐
                         │        FastAPI Backend        │
                         │        backend/main.py        │
                         │ Auth • Validation • API routes│
                         └───────────────┬───────────────┘
                                         │
                                         ▼
                         ┌───────────────────────────────┐
                         │           RAGService          │
                         │ Query rewrite + normalization │
                         │ Semantic + keyword retrieval  │
                         │ Hybrid ranking / filtering    │
                         │ Source selection + context    │
                         └───────────────┬───────────────┘
                                         │
                      ┌──────────────────┼──────────────────┐
                      ▼                  ▼                  ▼
              ┌────────────────┐ ┌────────────────┐ ┌────────────────┐
              │     Qdrant     │ │ Keyword Search │ │   ChatMemory   │
              │ Vector chunks  │ │ Retriever      │ │ Session history│
              └────────────────┘ └────────────────┘ └────────────────┘
                                         │
                                         ▼
                         ┌───────────────────────────────┐
                         │         LLM Service           │
                         │ Question + retrieved context  │
                         │ + conversation history        │
                         └───────────────┬───────────────┘
                                         │
                                         ▼
                         ┌───────────────────────────────┐
                         │ Answer + source metadata      │
                         │ returned to the frontend      │
                         └───────────────────────────────┘

### PDF Indexing Flow

PDF upload → text extraction → chunking + metadata → embeddings  
→ Qdrant vector storage  
→ original PDF in Supabase Storage  
→ document metadata saved

## 🛠️ Tech Stack

| Area | Technologies |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python, FastAPI, Pydantic, Uvicorn |
| RAG | Semantic retrieval, keyword retrieval, hybrid ranking |
| Vector Database | Qdrant |
| File Storage | Supabase Storage |
| Core Components | PDF processing, chunking, embeddings, chat memory |
| Testing | Python tests and retrieval evaluation |

## 🔄 How It Works

### 1. Document Ingestion

- A user uploads a PDF through the web interface.
- The backend extracts the document text.
- The text is split into chunks and enriched with metadata.
- Embeddings are generated for semantic retrieval.
- The chunks are indexed in Qdrant.
- The original PDF is stored in Supabase Storage, and document metadata is saved.

### 2. Question Answering

- The user asks a question about a document.
- The system normalizes and, where needed, rewrites the query.
- Semantic and keyword retrievers find relevant chunks.
- Hybrid ranking and filtering help select useful context.
- The LLM service generates a response using the question and retrieved context.
- The frontend receives the answer and source metadata.

### 3. Multi-Document Chat

Users can select multiple documents and ask questions across them. The backend validates document access and retrieves context from the selected documents.

## 📁 Important Project Structure

saathi/  
├── backend/  
│   ├── main.py  
│   ├── routes/  
│   │   ├── auth.py  
│   │   ├── ai_features.py  
│   │   ├── document_history.py  
│   │   └── podcast.py  
│   ├── services/  
│   │   ├── rag_service.py  
│   │   ├── rag_retriever.py  
│   │   ├── hybrid_retriever.py  
│   │   ├── keyword_retriever.py  
│   │   ├── embedding_service.py  
│   │   ├── qdrant_vector_store.py  
│   │   ├── chunker.py  
│   │   ├── pdf_service.py  
│   │   ├── llm_service.py  
│   │   ├── chat_memory.py  
│   │   ├── document_metadata.py  
│   │   ├── cloud_document_service.py  
│   │   └── supabase_client.py  
│   └── data/  
├── frontend/  
│   ├── index.html  
│   ├── login.html  
│   ├── style.css  
│   ├── app.js  
│   └── three/  
├── tests/  
│   ├── evaluate_retrieval.py  
│   └── test_rag_evaluation.py  
├── requirements.txt  
├── runtime.txt  
├── vercel.json  
├── conftest.py  
├── migrate_documents.py  
└── README.md

## 🔌 Main API Areas

- **Authentication** — Handles authentication-related operations.
- **AI Features** — Exposes AI feature endpoints.
- **Document History** — Supports document history operations.
- **Podcast** — Provides podcast-related functionality.
- **Chat and RAG** — Accepts questions, retrieves relevant document content, and returns answers with source information.

## 🔒 Security Notes

- Authenticate requests where required and validate document access before processing.
- Keep API keys and service credentials in environment configuration; do not commit secrets.
- Configure storage permissions carefully so users can only access their authorized documents.

## 🧪 Testing and Evaluation

The project includes Python tests and retrieval evaluation utilities. These help check application behavior and assess whether retrieval returns relevant document content.

## 🚀 Project Goal

Saathi AI aims to make document understanding easier by letting users ask natural-language questions and receive context-aware answers grounded in their uploaded documents.

---

*Saathi means "companion" in Hindi.*