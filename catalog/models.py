from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=200, verbose_name="Название темы")
    description = models.TextField(blank=True, verbose_name="Описание")

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.name

class Image(models.Model):
    title = models.CharField(max_length=200, verbose_name="Название")
    image = models.ImageField(upload_to='images/', verbose_name="Изображение")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name="Категория")
    description = models.TextField(blank=True, verbose_name="Описание")
    upload_date = models.DateTimeField(auto_now_add=True, verbose_name="Дата загрузки")

    class Meta:
        verbose_name = "Изображение"
        verbose_name_plural = "Изображения"

    def __str__(self):
        return self.title