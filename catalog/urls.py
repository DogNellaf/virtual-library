from django.urls import path
from catalog.views import index, category, file_download

urlpatterns = [
    path('', index, name='index'),
    path('category/<int:category_id>', category, name='category'),
    path('file/<int:file_id>/download/', file_download, name='file_download')
]