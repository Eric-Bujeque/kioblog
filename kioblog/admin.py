from django.contrib import admin
from markdownx.admin import MarkdownxModelAdmin

from kioblog import models


class PostAdmin(MarkdownxModelAdmin):
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("tags",)
    list_display = ("title", "category", "published", "draft", "is_featured")


class CategoryAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "featured")


class TagAdmin(admin.ModelAdmin):
    list_display = ("title", "slug")
    prepopulated_fields = {"slug": ("title",)}


class CommentAdmin(admin.ModelAdmin):
    list_display = ("username", "post", "parent", "created")


class MetaAdmin(admin.ModelAdmin):
    list_display = ("key", "value")


admin.site.register(models.Post, PostAdmin)
admin.site.register(models.Category, CategoryAdmin)
admin.site.register(models.Tag, TagAdmin)
admin.site.register(models.Comment, CommentAdmin)
admin.site.register(models.Meta, MetaAdmin)
