import uuid

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone


def paper_upload_path(instance, filename):
    """papers/user_<id>/<YYYY>/<MM>/<uuid>.pdf — original name is kept in Paper.title."""
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
