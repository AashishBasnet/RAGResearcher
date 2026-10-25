from pathlib import Path

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import Paper

MAX_UPLOAD_MB = 25


def count_pages(uploaded_file):
    """Return the PDF page count, or 0 if pypdf is missing or the file can't be read."""
    try:
        from pypdf import PdfReader

        uploaded_file.seek(0)
        total = len(PdfReader(uploaded_file).pages)
        uploaded_file.seek(0)
        return total
    except Exception:
        return 0


class PaperUploadForm(forms.ModelForm):
    class Meta:
        model = Paper
        fields = ["title", "file"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "input",
                    "placeholder": "Defaults to the file name",
                    "maxlength": 255,
                    "autocomplete": "off",
                }
            ),
            "file": forms.ClearableFileInput(
                attrs={"class": "dropzone__input", "accept": "application/pdf,.pdf"}
            ),
        }

    def clean_file(self):
        uploaded = self.cleaned_data["file"]

        if uploaded.size > MAX_UPLOAD_MB * 1024 * 1024:
            raise forms.ValidationError(f"The file is larger than {MAX_UPLOAD_MB} MB.")

        # Check the real content, not just the extension.
        header = uploaded.read(5)
        uploaded.seek(0)
        if header != b"%PDF-":
            raise forms.ValidationError("This doesn't look like a valid PDF file.")

        return uploaded

    def clean(self):
        cleaned = super().clean()
        uploaded = cleaned.get("file")
        if uploaded and not cleaned.get("title", "").strip():
            cleaned["title"] = Path(uploaded.name).stem[:255]
        return cleaned


class RegisterForm(UserCreationForm):
    """Username and password (typed twice, so a typo can't lock someone out)."""

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input"

        self.fields["username"].help_text = ""
        self.fields["username"].widget.attrs.update({"autocomplete": "username", "autofocus": True})

        self.fields["password1"].label = "Password"
        self.fields["password1"].help_text = ""
        self.fields["password1"].widget.attrs["autocomplete"] = "new-password"

        self.fields["password2"].label = "Confirm password"
        self.fields["password2"].help_text = ""
        self.fields["password2"].widget.attrs["autocomplete"] = "new-password"
