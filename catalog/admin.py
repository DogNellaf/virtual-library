from django.contrib import admin
from django.contrib.auth.models import User, Group
from catalog.models import Category, File

admin.site.site_header = "Виртуальное медио-хранилище"
admin.site.site_title = "Виртуальное медио-хранилище"
admin.site.index_title = "Добро пожаловать"

admin.site.unregister(User)
admin.site.unregister(Group)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(File)
class ImageAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'upload_date')
    list_filter = ('category', 'upload_date')
    search_fields = ('title', 'description')
    date_hierarchy = 'upload_date'