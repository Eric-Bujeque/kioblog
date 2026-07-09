import re

from django.db import models
from django.conf import settings
from django.utils import timezone

from markdownx.models import MarkdownxField

from kioblog.markdown.render import render_markdown


class Category(models.Model):
    title = models.CharField(max_length=250)
    slug = models.SlugField(max_length=200)
    featured = models.BooleanField(default=False)

    def __str__(self):
        return self.title

    def post_count(self):
        return self.post_set.filter(draft=False).count()

    class Meta:
        verbose_name_plural = "Categories"


class Tag(models.Model):
    title = models.CharField(max_length=60)
    slug = models.SlugField(max_length=200, unique=True)

    def __str__(self):
        return self.title


class Post(models.Model):
    title = models.CharField(max_length=250)
    content = MarkdownxField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    blocked = models.BooleanField(default=False)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    created = models.DateField(auto_now_add=True)
    published = models.DateTimeField(default=timezone.now)
    slug = models.SlugField(max_length=200)
    image = models.FileField(upload_to=settings.UPLOAD_TO, null=True)
    draft = models.BooleanField(default=False)
    tags = models.ManyToManyField(Tag, blank=True, related_name='posts')
    excerpt = models.TextField(blank=True)
    is_featured = models.BooleanField(default=False)
    meta_title = models.CharField(null=True, blank=True, max_length=250)
    meta_description = models.CharField(null=True, blank=True, max_length=250)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-published', '-id']

    def _render(self):
        if not hasattr(self, '_rendered'):
            self._rendered = render_markdown(self.content)
        return self._rendered

    @property
    def content_html(self):
        return self._render().html

    @property
    def toc(self):
        return self._render().toc

    @property
    def reading_time(self):
        words = len(re.sub(r'<[^>]+>', '', self.content_html).split())
        return max(1, round(words / 200))

    def first_paragraph(self):
        re_pattern = re.compile(r'(<p.*?</p>)')
        paragraphs = re_pattern.search(self.content)
        if not paragraphs:
            return ''
        return paragraphs.groups()[0]

    def get_previous(self):
        tie_break = models.Q(published__lt=self.published) | models.Q(published=self.published, id__lt=self.id)
        return Post.objects.filter(draft=False).filter(tie_break).order_by('-published', '-id').first()

    def get_next(self):
        tie_break = models.Q(published__gt=self.published) | models.Q(published=self.published, id__gt=self.id)
        return Post.objects.filter(draft=False).filter(tie_break).order_by('published', 'id').first()

    def related_posts(self, limit=4):
        qs = (Post.objects.filter(draft=False)
              .exclude(pk=self.pk)
              .filter(models.Q(category=self.category) | models.Q(tags__in=self.tags.all()))
              .distinct())
        return qs[:limit]

    @staticmethod
    def get_recent_posts(current_slug=None):
        recent_posts = Post.objects.filter(draft=False)
        if current_slug is not None:
            recent_posts = recent_posts.exclude(slug=current_slug)
        return recent_posts[:5]


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
