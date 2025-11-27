from django.shortcuts import render
from catalog.models import Image, Category

def index(request):
    categories = Category.objects.all()
    return render(request, 'catalog/index.html', {'categories': categories})

def image_list(request):
    category_id = request.GET.get('category')
    images = Image.objects.all()
    
    if category_id:
        images = images.filter(category_id=category_id)
    
    categories = Category.objects.all()
    return render(request, 'catalog/image_list.html', {
        'images': images,
        'categories': categories,
        'selected_category': int(category_id) if category_id else None
    })