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
        # TODO: queue the indexing job here, then set status to "indexed" when it finishes.
        messages.success(request, f"Uploaded {paper.title}.")
        return _redirect_back(request)

    # Invalid: re-render with errors and reopen the dialog.
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
    # TODO: also remove this paper's chunks from the vector store, e.g.
    #       collection.delete(where={"paper_id": paper.id})
    paper.file.delete(save=False)   # remove the PDF from storage
    paper.delete()                  # remove the database row
    messages.success(request, f"Deleted {title}.")
    return _redirect_back(request)


@require_POST
def logout_view(request):
    logout(request)
    return redirect("chatapp:chat")
