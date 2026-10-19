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
]
