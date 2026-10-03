import hashlib

from django import forms
from django.conf import settings
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Count
from django.http import FileResponse, Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import condition, require_GET, require_POST

from catalog import media, services
from catalog.models import Category, File, search_key

SORTS = {
    "new": (_("Newest first"), ("-upload_date", "-id")),
    "old": (_("Oldest first"), ("upload_date", "id")),
    "name": (_("Name, A to Z"), ("title_key", "id")),
    "-name": (_("Name, Z to A"), ("-title_key", "-id")),
    "size": (_("Smallest first"), ("size", "id")),
    "-size": (_("Largest first"), ("-size", "-id")),
}
VIEWS = {"grid": _("Grid"), "list": _("List")}
THEMES = {"auto": _("System"), "light": _("Light"), "dark": _("Dark")}
THEME_COOKIE = "theme"


class CatalogQuery(forms.Form):
    """The catalog state. It lives in the query string, so every view can be shared."""

    q = forms.CharField(required=False, max_length=100, strip=True)
    category = forms.IntegerField(required=False, min_value=1)
    kind = forms.ChoiceField(required=False, choices=File.Kind.choices)
    sort = forms.ChoiceField(required=False, choices=[(key, key) for key in SORTS])
    view = forms.ChoiceField(required=False, choices=list(VIEWS.items()))
    file = forms.IntegerField(required=False, min_value=1)

    def params(self) -> dict:
        # Invalid values are dropped one by one instead of rejecting the whole page.
        self.is_valid()
        return {key: self.cleaned_data.get(key) for key in self.fields}


@require_GET
def index(request):
    params = CatalogQuery(request.GET).params()

    categories = Category.objects.annotate(files_count=Count("files")).order_by("name")
    category = next((c for c in categories if c.pk == params["category"]), None)

    files = File.objects.select_related("category")
    if category is not None:
        files = files.filter(category=category)
    if params["q"]:
        files = files.filter(search_text__contains=search_key(params["q"]))
    kinds = _kind_counts(files)
    if params["kind"]:
        files = files.filter(kind=params["kind"])
    sort = params["sort"] or "new"
    files = files.order_by(*SORTS[sort][1])

    page = Paginator(files, settings.CATALOG_PAGE_SIZE).get_page(request.GET.get("page"))

    selected = None
    if params["file"]:
        selected = File.objects.select_related("category").filter(pk=params["file"]).first()

    return render(
        request,
        "catalog/index.html",
        {
            "categories": categories,
            "category": category,
            "total_count": sum(c.files_count for c in categories),
            "kinds": kinds,
            "kind": params["kind"],
            "q": params["q"] or "",
            "sort": sort,
            "sorts": {key: label for key, (label, _order) in SORTS.items()},
            "sort_label": SORTS[sort][0],
            "view": params["view"] or "grid",
            "views": VIEWS,
            "page": page,
            "selected": selected,
            "storage": services.storage_summary(),
        },
    )


def _kind_counts(files) -> list[tuple[str, str, int]]:
    counts = dict(files.order_by().values_list("kind").annotate(n=Count("id")))
    return [(kind, label, counts[kind]) for kind, label in File.Kind.choices if kind in counts]


@require_GET
def legacy_category(request, category_id):
    return redirect(f"{reverse('index')}?{urlencode({'category': category_id})}", permanent=True)


def _file_etag(request, file_id, *args, **kwargs):
    stored = File.objects.filter(pk=file_id).values_list("file", "thumbnail").first()
    if stored is None:
        return None
    return hashlib.sha256("|".join(stored).encode()).hexdigest()[:32]


def _send(field, *, content_type=None, as_attachment=False, filename=None):
    try:
        handle = field.open("rb")
    except FileNotFoundError:
        raise Http404 from None
    response = FileResponse(
        handle, as_attachment=as_attachment, filename=filename, content_type=content_type
    )
    response["Cache-Control"] = "private, max-age=300"
    return response


@require_GET
@condition(etag_func=_file_etag)
def file_thumbnail(request, file_id):
    file = get_object_or_404(File, pk=file_id)
    if not file.thumbnail:
        raise Http404
    return _send(file.thumbnail, content_type="image/webp")


@require_GET
@condition(etag_func=_file_etag)
def file_preview(request, file_id):
    """The original image, shown inline. Anything that is not a raster image is a 404."""
    file = get_object_or_404(File, pk=file_id, kind=File.Kind.IMAGE)
    content_type = media.image_content_type(file.file)
    if content_type is None:
        raise Http404
    return _send(file.file, content_type=content_type)


@require_GET
def file_download(request, file_id):
    file = get_object_or_404(File, pk=file_id)
    return _send(file.file, as_attachment=True, filename=file.download_name)


@require_GET
def favicon(request):
    return redirect(static("catalog/favicon.svg"), permanent=True)


@require_POST
def set_theme(request):
    theme = request.POST.get("theme")
    next_url = request.POST.get("next", "/")
    if not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        next_url = "/"
    response = HttpResponseRedirect(next_url)
    if theme in ("light", "dark"):
        response.set_cookie(
            THEME_COOKIE,
            theme,
            max_age=365 * 24 * 3600,
            samesite="Lax",
            secure=settings.SESSION_COOKIE_SECURE,
        )
    else:
        response.delete_cookie(THEME_COOKIE)
    return response


@never_cache
@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"status": "error", "database": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
