import re

from django.db import models
from django.conf import settings


class Category(models.Model):
    title = models.CharField(max_length=250)
    slug = models.SlugField(max_length=200)
    featured = models.BooleanField(default=False)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name_plural = "Categories"


class Post(models.Model):
    title = models.CharField(max_length=250)
    content = models.TextField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    blocked = models.BooleanField(default=False)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    created = models.DateField(auto_now_add=True)
    slug = models.SlugField(max_length=200)
    image = models.FileField(upload_to=settings.UPLOAD_TO, null=True)
    draft = models.BooleanField(default=False)
    meta_title = models.CharField(null=True, blank=True, max_length=250)
    meta_description = models.CharField(null=True, blank=True, max_length=250)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-id']

    def first_paragraph(self):
        re_pattern = re.compile(r'(<p.*?</p>)')
        paragraphs = re_pattern.search(self.content)
        if not paragraphs:
            return ''
        return paragraphs.groups()[0]

    @staticmethod
    def get_recent_posts():
        return Post.objects.all().order_by('-id')[:5]


class Comment(models.Model):
    username = models.CharField(max_length=100)
    content = models.TextField()
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    post = models.ForeignKey(Post, related_name='comments', on_delete=models.CASCADE)
    created = models.DateField(auto_now_add=True)
    email = models.EmailField()
    api = models.CharField(null=True, blank=True, max_length=50)

    def __str__(self):
        return '{} - {}'.format(self.username, self.post)


class Meta(models.Model):
    key = models.CharField(max_length=100)
    value = models.CharField(max_length=250, null=True)

    def __str__(self):
        return self.key
