from django.urls import path

from . import views

app_name = "chatapp"

urlpatterns = [
    # Public pages
    path("", views.landing_view, name="landing"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),

    # Projects (the logged-in home)
    path("projects/", views.projects_view, name="projects"),
    path("projects/create/", views.project_create_view, name="project_create"),
    path("projects/<int:project_id>/", views.project_view, name="project"),
    path("projects/<int:project_id>/rename/", views.project_rename_view, name="project_rename"),
    path("projects/<int:project_id>/delete/", views.project_delete_view, name="project_delete"),

    # Inside a project
    path("projects/<int:project_id>/papers/", views.project_papers_view, name="project_papers"),
    path("projects/<int:project_id>/papers/upload/", views.upload_paper_view, name="upload_paper"),
    path("projects/<int:project_id>/chat/ask/", views.ask_view, name="ask"),
    path("projects/<int:project_id>/chat/clear/", views.clear_chat_view, name="clear_chat"),

    # Individual papers
    path("papers/<int:pk>/file/", views.paper_file_view, name="paper_file"),
    path("papers/<int:pk>/delete/", views.delete_paper_view, name="delete_paper"),

    # Debugging (remove before deploying)
    path("embeddings/status/", views.store_status_view, name="debug_store_status"),
]
