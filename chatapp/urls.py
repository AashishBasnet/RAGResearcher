from django.urls import path

from . import views

app_name = "chatapp"

urlpatterns = [
    path("", views.chat_view, name="chat"),
    path("papers/", views.papers_view, name="papers"),
    path("papers/upload/", views.upload_paper_view, name="upload_paper"),
    path("papers/<int:pk>/file/", views.paper_file_view, name="paper_file"),
    path("papers/<int:pk>/delete/", views.delete_paper_view, name="delete_paper"),
    path("logout/", views.logout_view, name="logout"),
    path("papers/<int:pk>/delete/", views.delete_paper_view, name="delete_paper"),
    
    path("ingest_pdf/", views.pdf_ingestion_view, name = "ingest_pdf"),
    path("ingest-new/", views.ingest_new_papers_view, name="debug_ingest_new"),
    path("embeddings/status/", views.store_status_view, name="debug_store_status"),
    path("embeddings/cleanup/", views.cleanup_orphan_embeddings_view, name="debug_cleanup_orphans"),
    path("embeddings/<int:pk>/delete/", views.delete_embeddings_view, name="debug_delete_embeddings"),

]
