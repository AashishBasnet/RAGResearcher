import json
import logging

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import (
    FileResponse,
    Http404,
    HttpResponse,
    JsonResponse,
    StreamingHttpResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import MAX_UPLOAD_MB, PaperUploadForm, RegisterForm, count_pages
from .models import ChatMessage, Paper, Project
from .research_rag import generation, pdf_ingestor
from .research_rag.embeddings import get_embedder
from .research_rag.vector_store import get_vector_store

logger = logging.getLogger(__name__)

MAX_QUESTION_CHARS = 1000
MAX_PROJECT_NAME = 120


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_project(request, project_id):
    """A project, only if it belongs to the current user."""
    return get_object_or_404(Project, pk=project_id, owner=request.user)


def _project_context(request, project, form=None, **extra):
    return {
        "project": project,
        "papers": project.papers.all(),
        "upload_form": form or PaperUploadForm(),
        "max_upload_mb": MAX_UPLOAD_MB,
        **extra,
    }


def _redirect_back(request, fallback, *args):
    next_url = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect(fallback, *args)


def _text(body):
    return HttpResponse(body, content_type="text/plain; charset=utf-8")


def _source_url(source):
    """Link to the paper's PDF, opened at the page the passage came from."""
    if not source.get("paper_id"):
        return ""
    url = reverse("chatapp:paper_file", args=[source["paper_id"]])
    return f"{url}#page={source['page_number']}" if source.get("page_number") else url


def _adopt_legacy_data(user):
    """Papers and messages created before projects existed go into 'My first project'."""
    loose_papers = Paper.objects.filter(owner=user, project__isnull=True)
    loose_messages = ChatMessage.objects.filter(owner=user, project__isnull=True)
    if loose_papers.exists() or loose_messages.exists():
        project = Project.objects.create(owner=user, name="My first project")
        loose_papers.update(project=project)
        loose_messages.update(project=project)


# ---------------------------------------------------------------------------
# Public pages and accounts
# ---------------------------------------------------------------------------

def landing_view(request):
    if request.user.is_authenticated:
        return redirect("chatapp:projects")
    return render(request, "chatapp/landing.html")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("chatapp:projects")

    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("chatapp:projects")
    return render(request, "chatapp/registration/register.html", {"form": form})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("chatapp:landing")


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

@login_required
def projects_view(request):
    _adopt_legacy_data(request.user)
    projects = Project.objects.filter(owner=request.user).annotate(paper_count=Count("papers"))
    return render(request, "chatapp/projects.html", {"projects": projects})


@login_required
@require_POST
def project_create_view(request):
    name = request.POST.get("name", "").strip()[:MAX_PROJECT_NAME] or "Untitled project"
    project = Project.objects.create(owner=request.user, name=name)
    return redirect("chatapp:project", project_id=project.pk)


@login_required
@require_POST
def project_rename_view(request, project_id):
    project = _get_project(request, project_id)
    name = request.POST.get("name", "").strip()[:MAX_PROJECT_NAME]
    if name:
        project.name = name
        project.save(update_fields=["name", "updated_at"])
        messages.success(request, "Project renamed.")
    return redirect("chatapp:projects")


@login_required
@require_POST
def project_delete_view(request, project_id):
    project = _get_project(request, project_id)
    name = project.name

    store = get_vector_store()
    for paper in project.papers.all():
        store.delete_paper(paper.id)        # embeddings
        paper.file.delete(save=False)       # the PDF file
    project.delete()                        # papers and messages go with it

    messages.success(request, f"Deleted project {name}.")
    return redirect("chatapp:projects")


@login_required
def project_view(request, project_id):
    """The workspace: chat on the left, this project's papers on the right."""
    project = _get_project(request, project_id)
    recent = list(project.chat_messages.order_by("-created_at", "-id")[:50])
    recent.reverse()
    return render(request, "chatapp/chat.html", _project_context(request, project, chat_messages=recent))


@login_required
def project_papers_view(request, project_id):
    project = _get_project(request, project_id)
    return render(request, "chatapp/papers.html", _project_context(request, project))


# ---------------------------------------------------------------------------
# Papers: upload, open, delete
# ---------------------------------------------------------------------------

def ingest_single_paper(paper):
    """Load, chunk, embed and store one paper. Returns the number of chunks."""
    store = get_vector_store()
    embedding_manager = get_embedder()

    try:
        documents = pdf_ingestor.process_paper(paper)
        chunks = pdf_ingestor.split_documents(documents)
        if not chunks:
            raise ValueError("No extractable text found (scanned PDF?).")

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
@require_POST
def upload_paper_view(request, project_id):
    project = _get_project(request, project_id)
    form = PaperUploadForm(request.POST, request.FILES)

    if form.is_valid():
        paper = form.save(commit=False)
        paper.owner = request.user
        paper.project = project
        paper.pages = count_pages(paper.file)
        paper.save()
        project.save(update_fields=["updated_at"])   # moves the project to the top of the list

        try:
            chunks = ingest_single_paper(paper)
            messages.success(request, f"Uploaded and indexed {paper.title} ({chunks} chunks).")
        except Exception:
            messages.error(
                request,
                f"Uploaded {paper.title}, but indexing failed. Check the server terminal.",
            )

        return _redirect_back(request, "chatapp:project", project.pk)

    context = _project_context(request, project, form=form, open_upload=True)
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
    project_id = paper.project_id

    get_vector_store().delete_paper(paper.id)   # 1. embeddings
    paper.file.delete(save=False)               # 2. the PDF file
    paper.delete()                              # 3. the database row

    messages.success(request, f"Deleted {title}.")
    if project_id:
        return _redirect_back(request, "chatapp:project_papers", project_id)
    return redirect("chatapp:projects")


# ---------------------------------------------------------------------------
# Chat (one conversation per project)
# ---------------------------------------------------------------------------

@login_required
@require_POST
def ask_view(request, project_id):
    project = _get_project(request, project_id)
    user_id = request.user.id

    question = request.POST.get("question", "").strip()
    message_id = request.POST.get("message_id", "").strip()   # set on retry and edit

    paper_ids = list(project.papers.values_list("id", flat=True))
    if not paper_ids:
        return JsonResponse(
            {"error": "This project has no papers yet. Upload a PDF first, then ask your question."},
            status=400,
        )

    if message_id and not message_id.isdigit():
        return JsonResponse({"error": "Invalid message."}, status=400)

    chat = ChatMessage.objects.filter(project=project, owner_id=user_id)

    original = None
    if message_id:
        original = get_object_or_404(chat, pk=message_id, role=ChatMessage.Role.USER)
        question = question or original.content

    if not question:
        return JsonResponse({"error": "Please type a question."}, status=400)
    if len(question) > MAX_QUESTION_CHARS:
        return JsonResponse(
            {"error": f"Keep questions under {MAX_QUESTION_CHARS} characters."}, status=400
        )

    if original:
        # Cut the conversation back to this message; the answer is regenerated below.
        chat.filter(id__gte=original.id).delete()

    recent = list(chat.order_by("-created_at", "-id")[:6])
    history = [{"role": m.role, "content": m.content} for m in reversed(recent)]

    user_message = ChatMessage.objects.create(
        owner_id=user_id, project=project, role=ChatMessage.Role.USER, content=question
    )
    project.save(update_fields=["updated_at"])

    def event_stream():
        yield json.dumps({"type": "saved", "user_message_id": user_message.id}) + "\n"

        answer_parts, sources = [], []
        try:
            for event in generation.stream_rag_answer(
                question, owner_id=user_id, history=history, paper_ids=paper_ids
            ):
                kind = event["type"]
                if kind == "query":
                    logger.info("Searching for: %s", event["text"])
                elif kind == "sources":
                    for source in event["sources"]:
                        source["url"] = _source_url(source)
                    sources = event["sources"]
                elif kind == "token":
                    answer_parts.append(event["text"])
                yield json.dumps(event) + "\n"
        except Exception:
            logger.exception("Chat answer failed")
            yield json.dumps(
                {"type": "error", "message": "Something went wrong while answering. Check the server terminal."}
            ) + "\n"
            return

        ChatMessage.objects.create(
            owner_id=user_id,
            project=project,
            role=ChatMessage.Role.ASSISTANT,
            content="".join(answer_parts),
            sources=sources,
        )
        yield json.dumps({"type": "done"}) + "\n"

    response = StreamingHttpResponse(event_stream(), content_type="application/x-ndjson")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@login_required
@require_POST
def clear_chat_view(request, project_id):
    project = _get_project(request, project_id)
    ChatMessage.objects.filter(project=project, owner=request.user).delete()
    return redirect("chatapp:project", project_id=project.pk)


# ---------------------------------------------------------------------------
# Debugging (remove before deploying)
# ---------------------------------------------------------------------------

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