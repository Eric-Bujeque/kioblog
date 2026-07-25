from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.sitemaps.views import sitemap
from django.urls import path
from django.urls import include

from markdownx.views import ImageUploadView, MarkdownifyView

from kioblog import views
from kioblog import sitemap as blog_sitemap

generated_sitemap = {'posts': blog_sitemap.PostSitemap,
                     'categories': blog_sitemap.CategorySitemap,
                     'tags': blog_sitemap.TagSitemap,
                     'main': blog_sitemap.MainPageSitemap}

urlpatterns = [
    # KIOBLOG
    path('', views.HomeView.as_view(), name='kioblog-home'),
    path('page/<int:page>', views.HomeView.as_view(), name='kioblog-page'),
    path('category/<str:category>', views.HomeView.as_view(), name='kioblog-category'),
    path('category/<str:category>/page/<int:page>/', views.HomeView.as_view(), name='kioblog-category-page'),
    path('tag/<slug:tag>/', views.TagView.as_view(), name='kioblog-tag'),
    path('tag/<slug:tag>/page/<int:page>/', views.TagView.as_view(), name='kioblog-tag-page'),
    path('search/', views.SearchView.as_view(), name='kioblog-search'),
    path('<slug:slug>/', views.PostView.as_view(), name='kioblog-post'),

    # SEO
    path('robots.txt', include('robots.urls')),
    path('sitemap.xml', sitemap, {'sitemaps': generated_sitemap}, name='django.contrib.sitemaps.views.sitemap'),

    # MARKDOWN EDITOR
    # markdownx ships these views with no auth check of their own (anyone could
    # POST an image to ImageUploadView), so wrap them in staff_member_required
    # instead of including markdownx.urls directly. Same paths/names as
    # markdownx.urls so MARKDOWNX_URLS_PATH / MARKDOWNX_UPLOAD_URLS_PATH still line up.
    path('markdownx/upload/', staff_member_required(ImageUploadView.as_view()), name='markdownx_upload'),
    path('markdownx/markdownify/', staff_member_required(MarkdownifyView.as_view()), name='markdownx_markdownify'),
]
