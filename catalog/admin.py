from django.contrib import admin
from .models import Category, Image

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'upload_date')
    list_filter = ('category', 'upload_date')
    search_fields = ('title', 'description')
    date_hierarchy = 'upload_date'