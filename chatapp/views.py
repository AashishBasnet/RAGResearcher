from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from .forms import MAX_UPLOAD_MB, PaperUploadForm, count_pages
from .models import Paper

from .research_rag import pdf_ingestor
from django.http import HttpResponse

from .research_rag.embeddings import EmbeddingManager
from .research_rag.vector_store import get_vector_store
import logging
from .research_rag.embeddings import get_embedder

def _page_context(request, form=None, **extra):
    return {
        "papers": Paper.objects.filter(owner=request.user),
        "upload_form": form or PaperUploadForm(),
        "max_upload_mb": MAX_UPLOAD_MB,
        **extra,
    }


def _redirect_back(request, fallback="chatapp:papers"):
    next_url = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect(fallback)


@login_required
def chat_view(request):
    return render(request, "chatapp/chat.html", _page_context(request))


@login_required
def papers_view(request):
    return render(request, "chatapp/papers.html", _page_context(request))

@login_required
@require_POST
def upload_paper_view(request):
    form = PaperUploadForm(request.POST, request.FILES)

    if form.is_valid():
        paper = form.save(commit=False)
        paper.owner = request.user
        paper.pages = count_pages(paper.file)
        paper.save()

        try:
            chunks = ingest_single_paper(paper)
            messages.success(
                request,
                f"Uploaded and indexed {paper.title} ({chunks} chunks)."
            )
        except Exception:
            messages.error(
                request,
                f"Uploaded {paper.title}, but indexing failed. "
                "Check the server terminal."
            )

        return _redirect_back(request)

    context = _page_context(request, form=form, open_upload=True)
    return render(request, "chatapp/papers.html", context, status=400)


@login_required
def paper_file_view(request, pk):
    """Serve a PDF inline, only to the user who owns it."""
    paper = get_object_or_404(Paper, pk=pk, owner=request.user)
    try:
        handle = paper.file.open("rb")
    except FileNotFoundError:
        raise Http404("The PDF file is missing from storage.")
    return FileResponse(handle, content_type="application/pdf", filename=f"{paper.title or 'paper'}.pdf")


@login_required
@require_POST
def delete_paper_view(request, pk):
    paper = get_object_or_404(Paper, pk=pk, owner=request.user)
    title = paper.title

    get_vector_store().delete_paper(paper.id)   # 1. embeddings
    paper.file.delete(save=False)               # 2. the PDF file
    paper.delete()                              # 3. the database row

    messages.success(request, f"Deleted {title}.")
    return _redirect_back(request)

@require_POST
def logout_view(request):
    logout(request)
    return redirect("chatapp:chat")

from django.conf import settings

def user_papers_dir(user):
    return settings.MEDIA_ROOT / "papers" / f"user_{user.id}"

# in a view, where request.user is the current user:



@login_required
def pdf_ingestion_view(request):
    print("[INGEST] View entered", flush=True)

    try:
        papers = Paper.objects.filter(owner=request.user)
        print(f"[INGEST] Found {papers.count()} papers", flush=True)

        if not papers:
            return HttpResponse(
                "No papers uploaded yet.",
                content_type="text/plain"
            )

        print("[INGEST] Getting embedder...", flush=True)
        embedding_manager = get_embedder()

        print("[INGEST] Getting vector store...", flush=True)
        vector_store = get_vector_store()

        lines = []

        for paper in papers:
            print(
                f"[INGEST] Processing paper {paper.id}: {paper.title}",
                flush=True
            )

            documents = pdf_ingestor.process_paper(paper)
            print(f"[INGEST] Documents/pages: {len(documents)}", flush=True)

            chunks = pdf_ingestor.split_documents(documents)
            print(f"[INGEST] Chunks: {len(chunks)}", flush=True)

            texts = [chunk.page_content for chunk in chunks]
            print("[INGEST] Generating embeddings...", flush=True)

            embeddings = embedding_manager.generate_embeddings(texts)
            print(
                f"[INGEST] Embedding shape: {embeddings.shape}",
                flush=True
            )

            print("[INGEST] Adding to vector store...", flush=True)
            vector_store.add_documents(chunks, embeddings)

            lines.append(
                f"Paper {paper.id}: {len(documents)} pages, "
                f"{len(chunks)} chunks stored"
            )

        print("[INGEST] Completed successfully", flush=True)
        return HttpResponse("\n".join(lines), content_type="text/plain")

    except Exception:
        import traceback
        traceback.print_exc()
        return HttpResponse(
            "PDF ingestion failed. Check the server terminal.",
            status=500,
            content_type="text/plain"
        )


logger = logging.getLogger(__name__)


def _text(body):
    return HttpResponse(body, content_type="text/plain; charset=utf-8")

def ingest_single_paper(paper):
    store = get_vector_store()
    embedding_manager = get_embedder()

    try:
        documents = pdf_ingestor.process_paper(paper)
        chunks = pdf_ingestor.split_documents(documents)

        texts = [chunk.page_content for chunk in chunks]
        embeddings = embedding_manager.generate_embeddings(texts)

        store.add_documents(chunks, embeddings)

        paper.pages = len(documents)
        paper.status = Paper.Status.INDEXED
        paper.save(update_fields=["pages", "status"])

        return len(chunks)

    except Exception:
        logger.exception("Embedding failed for paper %s", paper.id)
        paper.status = Paper.Status.FAILED
        paper.save(update_fields=["status"])
        raise

@login_required
def ingest_new_papers_view(request):
    """Embed only the papers that are not in the vector store yet."""
    store = get_vector_store()
    already = store.chunk_counts_by_paper(owner_id=request.user.id)
    new_papers = Paper.objects.filter(owner=request.user).exclude(pk__in=already.keys())

    if not new_papers:
        return _text("Nothing new to embed. Every paper is already in the vector store.")

    embedding_manager = get_embedder()      # loaded only when there is work to do
    lines = []

    for paper in new_papers:
        print(f"\n=== NEW paper {paper.id}: {paper.title} ===")
        try:
            documents = pdf_ingestor.process_paper(paper)
            chunks = pdf_ingestor.split_documents(documents)

            texts = [chunk.page_content for chunk in chunks]
            embeddings = embedding_manager.generate_embeddings(texts)
            print(embeddings.shape)

            store.add_documents(chunks, embeddings)

            paper.pages = len(documents)
            paper.status = Paper.Status.INDEXED
            lines.append(f"Paper {paper.id}: {len(chunks)} chunks stored")
        except Exception:
            logger.exception("Embedding failed for paper %s", paper.id)
            paper.status = Paper.Status.FAILED
            lines.append(f"Paper {paper.id}: FAILED (see the terminal)")
        paper.save(update_fields=["status", "pages"])

    return _text("\n".join(lines))


@login_required
def delete_embeddings_view(request, pk):
    """Remove one paper's embeddings. The paper itself stays in the list."""
    paper = get_object_or_404(Paper, pk=pk, owner=request.user)
    store = get_vector_store()

    before = store.chunk_counts_by_paper(owner_id=request.user.id).get(paper.id, 0)
    store.delete_paper(paper.id)

    paper.status = Paper.Status.PROCESSING
    paper.save(update_fields=["status"])

    message = f"Paper {paper.id}: removed {before} chunks from the store."
    print(message)
    return _text(message)


@login_required
def cleanup_orphan_embeddings_view(request):
    """Remove chunks that belong to papers which no longer exist (deleted PDFs)."""
    store = get_vector_store()
    in_store = store.chunk_counts_by_paper(owner_id=request.user.id)
    existing = set(Paper.objects.filter(owner=request.user).values_list("id", flat=True))

    orphans = {pid: n for pid, n in in_store.items() if pid not in existing}
    for pid in orphans:
        store.delete_paper(pid)

    if not orphans:
        return _text("No orphaned embeddings found.")

    lines = [f"Paper {pid}: removed {n} orphaned chunks" for pid, n in orphans.items()]
    print("\n".join(lines))
    return _text("\n".join(lines))


@login_required
def store_status_view(request):
    """Show what is in the vector store compared to your papers."""
    store = get_vector_store()
    in_store = store.chunk_counts_by_paper(owner_id=request.user.id)
    papers = {p.id: p for p in Paper.objects.filter(owner=request.user)}

    lines = [f"Total chunks in the store (all users): {store.index.ntotal}", ""]
    for paper_id, paper in papers.items():
        n = in_store.get(paper_id, 0)
        lines.append(f"Paper {paper_id} {paper.title!r}: {n} chunks" + ("" if n else "   <- NOT embedded"))
    for paper_id, n in in_store.items():
        if paper_id not in papers:
            lines.append(f"Paper {paper_id}: {n} chunks   <- ORPHAN (paper was deleted)")

    return _text("\n".join(lines))