# RAGResearcher 📚

**A Retrieval-Augmented Generation (RAG) application for research papers, built with Django, Python, and FAISS.**

RAGResearcher is a web application designed to help users manage research papers and, ultimately, ask questions about their contents using Retrieval-Augmented Generation (RAG).

Users can upload PDF research papers, automatically extract and split their contents into chunks, generate semantic embeddings, and store those embeddings in a FAISS vector index. The application also supports deleting research papers and their associated vector data.

The next development phase focuses on semantic retrieval and AI-powered question answering grounded in the uploaded research papers.

## ✨ Features

### Implemented

- **PDF Upload:** Upload research papers through the web interface.
- **Paper Management:** Store paper information and associate papers with individual users.
- **PDF Processing:** Extract text and process uploaded PDF documents.
- **Text Chunking:** Split document content into smaller chunks suitable for semantic retrieval.
- **Embedding Generation:** Generate vector embeddings using the `all-MiniLM-L6-v2` sentence-transformer model.
- **FAISS Vector Storage:** Store document embeddings in a persistent FAISS index.
- **Automatic Indexing:** Automatically process and index a paper after a successful upload.
- **Incremental Indexing:** Identify papers that have not yet been indexed and process them without re-indexing existing papers unnecessarily.
- **Paper Deletion:** Delete a paper, its uploaded PDF file, and its associated embeddings.
- **Index Status Checking:** Inspect stored chunk counts and identify papers that have not been indexed.
- **User Authentication:** Protect paper-management and ingestion views using Django authentication.
- **Per-User Retrieval Filtering:** Filter retrieved vector-search results by the document owner's ID.

### Planned

- Semantic retrieval of relevant research-paper chunks.
- AI-powered question answering using retrieved context.
- A chat interface for asking questions about uploaded papers.
- Source references, including paper titles and page numbers where available.
- Conversation history and follow-up questions.

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core programming language |
| Django | Web framework and application backend |
| FAISS | Vector indexing and similarity search |
| Sentence Transformers | Semantic embedding generation |
| `all-MiniLM-L6-v2` | Text embedding model |
| NumPy | Numerical operations on embeddings |
| PyMuPDF / PyPDF | PDF processing |
| LangChain packages | Supporting document-processing and RAG components |
| SQLite or configured Django database | Application data persistence |

The actual database engine depends on the project's Django settings.

## 🏗️ How It Works

The current PDF ingestion pipeline follows these steps:

```text
                  User uploads PDF
                         |
                         v
                  Django upload view
                         |
                         v
                  Save Paper record
                         |
                         v
                  Extract PDF text
                         |
                         v
                   Split into chunks
                         |
                         v
                  Generate embeddings
                    (384 dimensions)
                         |
                         v
                   Store in FAISS
                         |
                         v
                 Mark paper as indexed
```

The planned question-answering pipeline will extend the existing system:

```text
                   User asks a question
                            |
                            v
                   Generate query embedding
                            |
                            v
                   Search FAISS index
                            |
                            v
                   Retrieve relevant chunks
                            |
                            v
                   Build context for the LLM
                            |
                            v
                   Generate grounded answer
                            |
                            v
                   Display answer and sources
```

The retrieval and question-answering pipeline is still under development.

## 📂 Project Structure

The following is a conceptual overview of the main project components. Exact filenames and directories may vary as development continues.

```text
RAGResearcher/
├── manage.py
├── requirements.txt
├── vectorstore/
│   ├── index.faiss
│   └── records.pkl
├── media/
│   └── papers/
└── chatapp/
    ├── models.py
    ├── views.py
    ├── urls.py
    ├── forms.py
    └── templates/
        └── chatapp/
            └── papers.html
```

### Important components

- `models.py` — Defines application data models, including research papers.
- `views.py` — Handles paper uploads, ingestion, deletion, and index management.
- `forms.py` — Provides forms for uploading research papers.
- `urls.py` — Maps URLs to Django views.
- `papers.html` — Provides the paper-management interface.
- `vectorstore/index.faiss` — Persistent FAISS vector index.
- `vectorstore/records.pkl` — Stores document chunks and their metadata.

**Note:** This is an illustrative structure, not a verified listing of every file in the repository.

## ⚙️ Installation and Setup

### Prerequisites

- Python 3.12 or a compatible Python version.
- Git.
- A supported operating system.
- Sufficient disk space for uploaded PDFs, embedding models, and vector data.

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/RAGResearcher.git
cd RAGResearcher
```

Replace `YOUR_USERNAME` with your GitHub username.

### 2. Create a virtual environment

On Windows:

```powershell
python -m venv env
.\env\Scripts\Activate.ps1
```

If you're using Command Prompt instead of PowerShell:

```bat
env\Scripts\activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

The current dependency list includes Django, LangChain packages, PDF-processing libraries, Sentence Transformers, NumPy through its dependencies, and `faiss-cpu`.

### 4. Configure environment variables

If the project uses environment variables, create a local `.env` file based on the configuration expected by your Django settings.

Do not commit secret keys, API keys, passwords, or other sensitive configuration values.

### 5. Apply database migrations

```bash
python manage.py migrate
```

### 6. Start the development server

```bash
python manage.py runserver
```

Open the local development address shown in the terminal, usually:

`http://127.0.0.1:8000/`

The exact page depends on the project's URL configuration.

**First run:** The embedding model may need to be downloaded, so initial embedding generation can take longer.

## 📄 PDF Management

The current application supports the following workflow:

1. Open the Papers section.
2. Upload a research paper in PDF format.
3. The application saves the paper and processes its contents.
4. The embedding model generates vector representations for the chunks.
5. FAISS stores the embeddings and associated metadata.
6. The paper's status is updated to indicate successful indexing or failure.
7. Delete the paper when it is no longer needed; its file, database record, and associated vector data are removed.

The application also includes a view for indexing previously uploaded papers that are not yet represented in the vector store.

## 🧠 Vector Storage and Embeddings

RAGResearcher uses FAISS for vector similarity search and `all-MiniLM-L6-v2` for generating embeddings.

The embedding model produces **384-dimensional vectors**.

The FAISS index and its metadata are persisted locally:

- `index.faiss` stores the vector index.
- `records.pkl` stores the corresponding document records and metadata.

Metadata includes information such as the paper ID, owner ID, and chunk information.

The current search implementation uses squared L2 distance and filters results by owner ID. The final retrieval pipeline will need to connect this functionality to the question-answering workflow.

### Important storage considerations

- Keep the FAISS index and metadata file together.
- Back up both files when preserving the indexed data.
- Do not manually edit `records.pkl`.
- Treat the pickle file as trusted local data only; loading untrusted pickle files can execute malicious code.
- In a multi-user or production deployment, ensure access controls are enforced consistently across paper management, indexing, deletion, and retrieval.
- Keep uploaded PDFs and vector data in persistent storage if the application is deployed on infrastructure with ephemeral filesystems.

## 🔒 Security and Privacy

Research papers may contain unpublished or sensitive information. Consider the following before deploying the application publicly:

- Require authentication for private paper-management operations.
- Verify paper ownership before accessing, deleting, or retrieving a user's documents.
- Keep Django's production `DEBUG` setting disabled.
- Configure allowed hosts, HTTPS, secret keys, and environment variables appropriately.
- Protect uploaded files from unauthorized access.
- Avoid committing uploaded PDFs, local databases, credentials, or generated vector-store data unless explicitly intended.
- Validate PDF uploads and enforce appropriate file-size limits.

The vector-search filtering currently checks document ownership in the search results. This is not a substitute for comprehensive authorization throughout the application.

## 🚧 Development Roadmap

- [x] Django project and paper-management interface
- [x] PDF upload and persistence
- [x] PDF text extraction and chunking
- [x] Embedding generation with Sentence Transformers
- [x] Persistent FAISS vector storage
- [x] Automatic indexing after PDF upload
- [x] Incremental indexing of unindexed papers
- [x] Paper deletion and associated vector cleanup
- [x] Index status and chunk-count inspection
- [ ] Complete semantic retrieval workflow
- [ ] Integrate retrieval with a language model
- [ ] Build the research-paper QA chat interface
- [ ] Return answers grounded in retrieved document content
- [ ] Display source papers and page references
- [ ] Add conversation history and follow-up questions
- [ ] Improve error handling and production deployment

## 🎯 Project Goal

The goal of RAGResearcher is to make research papers easier to explore by allowing users to ask natural-language questions and receive answers grounded in the contents of their uploaded documents.

Rather than relying exclusively on a language model's general knowledge, the planned RAG workflow will retrieve relevant passages from the user's research papers and use those passages as context for generating answers.

## 🤝 Contributing

Contributions, suggestions, and bug reports are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Make your changes.
4. Test the changes.
5. Submit a pull request.

## 📜 License

This project is licensed under the [MIT License](LICENSE).

You are free to use, copy, modify, merge, publish, distribute, sublicense, and sell copies of this software, subject to the terms and conditions of the MIT License. See the [LICENSE](LICENSE) file for details.


---

**Project:** RAGResearcher  
**Status:** PDF management and vector indexing implemented; retrieval and question-answering chat under development.
