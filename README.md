# kioblog
Reusable blog app for Django
# Installation
1. Install the package
```bash
pip install kioblog
```
2. Add the app to your installed apps
```python
INSTALLED_APPS = [
    ...
    'django.contrib.sites',
    'django.contrib.sitemaps',
    'kioblog',
    ...
]
```
3. Add the app's urls to your project's urls
```python
urlpatterns = [
    ...
    path('blog/', include('kioblog.urls')),
    ...
]
```
4. Run the migrations
```bash
python manage.py migrate
```
5. Create a superuser
```bash
python manage.py createsuperuser
```
6. Start the development server
```bash
python manage.py runserver
```
7. Visit the admin page
```
http://localhost:8000/admin
```
8. Create a new blog post
