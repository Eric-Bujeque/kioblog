from django.contrib.sitemaps.views import sitemap
from django.contrib import admin
from django.urls import path
from django.urls import include
from django.conf import settings
from django.conf.urls.static import static

from kioblog import views
# from kioblog import sitemap as blog_sitemap

# generated_sitemap = {'posts': blog_sitemap.BlogSitemap,
#                      'main': blog_sitemap.MainPageSitemap}

urlpatterns = [
    # APP
    path('', views.HomeView.as_view(), name='kioblog-home'),
    path('page/<int:page>', views.HomeView.as_view(), name='kioblog-page'),
    path('category/<str:category>', views.HomeView.as_view(), name='kioblog-category'),
    path('<slug:slug>/', views.PostView.as_view(), name='kioblog-post'),

    # SEO
    path('robots.txt', include('robots.urls')),
    # path('sitemap.xml', sitemap, {'sitemaps': generated_sitemap}, name='django.contrib.sitemaps.views.sitemap'),

    # SUMMERNOTE
    path('summernote/', include('django_summernote.urls')),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
