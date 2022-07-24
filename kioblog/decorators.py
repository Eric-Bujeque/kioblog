from kioblog import models


def load_recent_posts(view):
    def wrapper(request, *args, **kwargs):
        r = view(request, *args, **kwargs)
        current_slug = kwargs.get('slug', None)
        r.context_data.update({'recent_posts': models.Post.get_recent_posts(current_slug)})
        return r.render()
    return wrapper
