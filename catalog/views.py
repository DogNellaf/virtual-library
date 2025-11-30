from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from catalog.models import File, Category
from django.conf import settings


def _storage_info():
    """
    Суммирует реальные размеры файлов из storage в Python.
    Подходит если у вас умеренное количество записей.
    """
    used = 0
    # используем only('file') чтобы немного оптимизировать выборку полей
    for f in File.objects.all().only('file'):
        try:
            # f.file может быть FieldFile, у которого есть .size
            size = getattr(f.file, 'size', 0) or 0
            used += int(size)
        except Exception:
            # если файл отсутствует в storage или storage возвращает ошибку — пропускаем
            continue

    quota = getattr(settings, 'STORAGE_QUOTA_BYTES', 0)
    percent = round(used / quota, 1)

    bytes_in_gb = 8 * 1024 * 1024 * 1024
    storage_used = round(used / bytes_in_gb, 2)
    storage_total_gb = round(quota / bytes_in_gb, 2)

    print("Storage used:", storage_used, "TB of", storage_total_gb, "TB (", percent, "% )")

    return {
        'used': storage_used,
        'total_gb': storage_total_gb,
        'percent': str(percent).replace(',', '.')
    }

def index(request):
    categories = Category.objects.all()
    files = File.objects.all()
    storage = _storage_info()

    return render(
        request, 'catalog/base.html', {
            'categories': categories,
            'files': files,
            'storage_used': storage['used'],
            'storage_total_gb': storage['total_gb'],
            'storage_percent': storage['percent']
        }
    )

def category(request, category_id):
    categories = Category.objects.all()
    get_object_or_404(Category, id=category_id)
    files = File.objects.filter(category_id=category_id)
    storage = _storage_info()

    return render(request, 'catalog/base.html', {
        'files': files,
        'categories': categories,
        'selected_category_id': int(category_id) if category_id else None,
        'storage_used': storage['used'],
        'storage_total_gb': storage['total_gb'],
        'storage_percent': storage['percent']
    })

def file_download(request, file_id):
    file = get_object_or_404(File, id=file_id)
    response = HttpResponse(file.file, content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{file.title}"'
    return response