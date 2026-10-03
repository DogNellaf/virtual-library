from django import forms
from django.conf import settings
from django.contrib import admin
from django.db.models import Count
from django.template.defaultfilters import filesizeformat
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from catalog import services
from catalog.models import Category, File, Storage

admin.site.site_header = _("Media library")
admin.site.site_title = _("Media library")
admin.site.index_title = _("Administration")
admin.site.site_url = "/"


class FileAdminForm(forms.ModelForm):
    class Meta:
        model = File
        fields = ["title", "category", "file", "description"]
        # Stored files have no public URL, so the "Currently: <link>" widget is replaced by
        # a plain input and a download link in the read-only section.
        widgets = {"file": forms.FileInput}

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if "file" in self.changed_data and upload.size > settings.FILE_UPLOAD_MAX_BYTES:
            raise forms.ValidationError(
                gettext("The file is too large. The limit is %(limit)s.")
                % {"limit": filesizeformat(settings.FILE_UPLOAD_MAX_BYTES)}
            )
        return upload

    def clean(self):
        cleaned = super().clean()
        upload = cleaned.get("file")
        if upload and "file" in self.changed_data:
            # The admin wraps the whole add/change view in a transaction, so the storage
            # row locked here stays locked until the file is saved.
            try:
                services.reserve_space(upload.size, replacing=self.instance)
            except services.QuotaExceeded as error:
                self.add_error("file", error)
        return cleaned


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "files_count", "description"]
    search_fields = ["name"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(files_count=Count("files"))

    @admin.display(description=_("files"), ordering="files_count")
    def files_count(self, obj):
        url = reverse("admin:catalog_file_changelist") + f"?category__id__exact={obj.pk}"
        return format_html('<a href="{}">{}</a>', url, obj.files_count)


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    form = FileAdminForm
    list_display = ["preview", "title", "category", "kind", "human_size", "upload_date"]
    list_display_links = ["preview", "title"]
    list_filter = ["category", "kind", "upload_date"]
    list_select_related = ["category"]
    search_fields = ["title", "description", "original_name"]
    date_hierarchy = "upload_date"
    readonly_fields = ["preview", "download", "kind", "human_size", "dimensions", "upload_date"]
    fieldsets = [
        (None, {"fields": ["title", "category", "file", "description"]}),
        (_("Stored file"), {"fields": readonly_fields}),
    ]

    def get_fieldsets(self, request, obj=None):
        return self.fieldsets if obj else self.fieldsets[:1]

    @admin.display(description=_("preview"))
    def preview(self, obj):
        if not obj.thumbnail:
            return obj.extension or "—"
        return format_html(
            '<img src="{}" alt="" class="file-thumb">', reverse("file_thumbnail", args=[obj.pk])
        )

    @admin.display(description=_("original name"))
    def download(self, obj):
        return format_html(
            '<a href="{}">{}</a>', reverse("file_download", args=[obj.pk]), obj.download_name
        )

    @admin.display(description=_("size"), ordering="size")
    def human_size(self, obj):
        return filesizeformat(obj.size)

    @admin.display(description=_("dimensions"))
    def dimensions(self, obj):
        return f"{obj.width} × {obj.height} px" if obj.width else "—"

    def view_on_site(self, obj):
        return obj.get_absolute_url()

    class Media:
        css = {"all": ["catalog/admin.css"]}


@admin.register(Storage)
class StorageAdmin(admin.ModelAdmin):
    list_display = ["__str__", "used", "quota"]
    fields = ["quota_bytes", "used", "quota"]
    readonly_fields = ["used", "quota"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        Storage.load()
        return super().get_queryset(request)

    @admin.display(description=_("used"))
    def used(self, obj):
        return filesizeformat(services.used_bytes())

    @admin.display(description=_("quota"))
    def quota(self, obj):
        return filesizeformat(obj.quota_bytes) if obj.quota_bytes else gettext("No limit")
