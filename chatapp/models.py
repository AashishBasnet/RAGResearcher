import uuid

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone


class Project(models.Model):
    """A workspace: its own papers and its own conversation."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    name = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name

    @property
    def color_index(self):
        """Picks one of six card colours; stable for a given project."""
        return self.pk % 6


def paper_upload_path(instance, filename):
    """papers/user_<id>/<YYYY>/<MM>/<uuid>.pdf — the original name is kept in Paper.title."""
    ext = filename.rsplit(".", 1)[-1].lower()
    date = timezone.now().strftime("%Y/%m")
    return f"papers/user_{instance.owner_id}/{date}/{uuid.uuid4().hex}.{ext}"


class Paper(models.Model):
    class Status(models.TextChoices):
        PROCESSING = "processing", "Processing"
        INDEXED = "indexed", "Indexed"
        FAILED = "failed", "Failed"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="papers",
    )
    # null=True only so papers uploaded before projects existed keep working;
    # projects_view moves them into a "My first project" automatically.
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="papers",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255, blank=True)
    file = models.FileField(
        upload_to=paper_upload_path,
        validators=[FileExtensionValidator(["pdf"])],
    )
    pages = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PROCESSING,
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.title or self.file.name


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_messages",
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="chat_messages",
        null=True,
        blank=True,
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    sources = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.role}: {self.content[:40]}"
