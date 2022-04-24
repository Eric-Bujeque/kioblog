from django.contrib import admin

from django_summernote.admin import SummernoteModelAdmin

from kioblog import models


class PostAdmin(SummernoteModelAdmin):
    prepopulated_fields = {"slug": ("title",)}
    summernote_fields = ('content',)


class CategoryAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'featured')


class CommentAdmin(admin.ModelAdmin):
    list_display = ('username', 'post', 'parent', 'created')
    summernote_fields = ('content',)


class MetaAdmin(admin.ModelAdmin):
    list_display = ('key', 'value')


admin.site.register(models.Post, PostAdmin)
admin.site.register(models.Category, CategoryAdmin)
admin.site.register(models.Comment, CommentAdmin)
admin.site.register(models.Meta, MetaAdmin)
