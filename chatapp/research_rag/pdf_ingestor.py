import os
from langchain_community.document_loaders import PyPDFLoader,PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter   
from pathlib import Path

# Read all the pdfs inside the directory
def process_all_pdfs(pdf_directory):
    all_documents = []
    pdf_dir = Path(pdf_directory)

    #find all PDF files recursively
    pdf_files = list(pdf_dir.glob("**/*.pdf"))

    print(f"found{len(pdf_files)} PDF files to process")

    for pdf_file in pdf_files:
        print(f"\nProcessing: {pdf_file.name}")
        try:
            loader = PyPDFLoader(str(pdf_file))
            documents = loader.load()

            #Add source information to metadata
            for doc in documents:
                doc.metadata['source_file'] = pdf_file.name
                doc.metadata['file_type'] = 'pdf'

            all_documents.extend(documents)
            print(f"    Loaded{len(documents)} pages")
        
        except Exception as e:
            print(f"    Error:{e}")
    
    print(f"\nTotal documents loaded:{len(all_documents)}")

    return all_documents


# Text splitting get into Chunks
def split_documents(documents,chunk_size=1000,chunk_overlap=200):
    """smaller chunk = better RAG performance"""
    text_splitter = RecursiveCharacterTextSplitter( #name of text splitter we are using
        chunk_size = chunk_size,
        chunk_overlap=chunk_overlap,
        length_function = len,
        separators=["\n\n","\n"," ", ""]
    )
    split_docs = text_splitter.split_documents(documents)
    print(f"Split {len(documents)} documents into {len(split_docs)} chunks")

    # Here is an example of a chunk:
    if split_docs:
        print(f"\nExample Chunk:")
        print(f"Content: {split_docs[0].page_content[:200]}...")
        print(f"Metadata: {split_docs[0].metadata}")

    return split_docs

def process_paper(paper):
    """Load ONE paper's PDF and tag every page with the ids needed for search/delete."""
    documents = PyPDFLoader(paper.file.path).load()
    for doc in documents:
        doc.metadata["source_file"] = Path(paper.file.name).name
        doc.metadata["file_type"] = "pdf"
        doc.metadata["paper_id"] = paper.id
        doc.metadata["owner_id"] = paper.owner_id
        doc.metadata["paper_title"] = paper.title
    print(f"Loaded {len(documents)} pages from: {paper.title}")
    return documents