from django.urls import path

from catalog import views

urlpatterns = [
    path("", views.index, name="index"),
    path("category/<int:category_id>", views.legacy_category),
    path("files/<int:file_id>/thumbnail/", views.file_thumbnail, name="file_thumbnail"),
    path("files/<int:file_id>/preview/", views.file_preview, name="file_preview"),
    path("files/<int:file_id>/download/", views.file_download, name="file_download"),
    path("theme/", views.set_theme, name="set_theme"),
    path("health/", views.health, name="health"),
    path("favicon.ico", views.favicon),
]
