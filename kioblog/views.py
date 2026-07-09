from django.db.models import Q
from django.views import generic
from django.core.paginator import Paginator
from django.utils.decorators import method_decorator

from kioblog import models
from kioblog import decorators


class HomeView(generic.TemplateView):
    template_name = 'kioblog/home.html'

    def get_context_data(self, **kwargs):
        category_slug = kwargs.get('category', False)
        page = kwargs.get('page', 1)
        posts = models.Post.objects.filter(draft=False)

        category = None
        if category_slug:
            category = models.Category.objects.filter(slug=category_slug).first()
            posts = posts.filter(category__slug=category_slug)

        paginator = Paginator(posts, 5)
        data = {'posts': paginator.get_page(page),
                'page_range': range(1, paginator.num_pages + 1),
                'recent_posts': models.Post.get_recent_posts(),
                'category': category,
                'featured_post': models.Post.objects.filter(draft=False, is_featured=True).first()}

        return data


class TagView(generic.TemplateView):
    template_name = 'kioblog/home.html'

    def get_context_data(self, **kwargs):
        tag_slug = kwargs.get('tag')
        page = kwargs.get('page', 1)
        tag = models.Tag.objects.filter(slug=tag_slug).first()
        posts = models.Post.objects.filter(draft=False, tags__slug=tag_slug)
        paginator = Paginator(posts, 5)
        return {'posts': paginator.get_page(page),
                'page_range': range(1, paginator.num_pages + 1),
                'recent_posts': models.Post.get_recent_posts(),
                'tag': tag}


class SearchView(generic.TemplateView):
    template_name = 'kioblog/search.html'

    def get_context_data(self, **kwargs):
        query = self.request.GET.get('q', '').strip()
        posts = models.Post.objects.none()
        if query:
            posts = models.Post.objects.filter(draft=False).filter(Q(title__icontains=query) | Q(excerpt__icontains=query) | Q(content__icontains=query))
        return {'query': query,
                'posts': posts,
                'count': posts.count(),
                'recent_posts': models.Post.get_recent_posts()}


@method_decorator(decorators.load_recent_posts, name='dispatch')
class PostView(generic.DetailView):
    template_name = 'kioblog/post.html'
    model = models.Post

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        post = self.object
        context['prev_post'] = post.get_previous()
        context['next_post'] = post.get_next()
        context['related_posts'] = post.related_posts()
        return context
