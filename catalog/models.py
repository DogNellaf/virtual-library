from django.db import models

class Category(models.Model):
    name = models.CharField(
        max_length=200,
        verbose_name="Название темы"
    )

    description = models.TextField(
        blank=True,
        verbose_name="Описание"
    )

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.name

class File(models.Model):
    title = models.CharField(
        max_length=200,
        verbose_name="Название"
    )

    file = models.ImageField(
        upload_to='uploads/',
        verbose_name="Файл"
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        verbose_name="Категория"
    )

    description = models.TextField(
        blank=True,
        verbose_name="Описание"
    )

    upload_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата загрузки"
    )

    class Meta:
        verbose_name = "Файл"
        verbose_name_plural = "Файлы"

    @property
    def format(self):
        return self.file.name.split('.')[-1].upper()

    @property
    def size(self):
        return self.file.size

    @property
    def size_mb(self):
        return round(self.file.size * 100 / (8 * 1024 * 1024)) / 100

    @property
    def is_image(self):
        return self.format.lower() in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp']

    def __str__(self):
        return self.title