from django.core.exceptions import ImproperlyConfigured
from django.template.base import TemplateDoesNotExist
from django.template.loader import BaseLoader, get_template_from_string, find_template_loader, make_origin
from django.utils.hashcompat import sha_constructor
from django.utils.importlib import import_module
from django_mobile import get_flavour
from django_mobile.conf import settings


class Loader(BaseLoader):
    is_usable = True

    def __init__(self, *args, **kwargs):
        loaders = []
        for loader_name in settings.FLAVOURS_TEMPLATE_LOADERS:
            loader = find_template_loader(loader_name)
            if loader is not None:
                loaders.append(loader)
        self.template_source_loaders = tuple(loaders)
        super(BaseLoader, self).__init__(*args, **kwargs)

    def prepare_template_name(self, template_name):
        template_name = u'%s/%s' % (get_flavour(), template_name)
        if settings.FLAVOURS_TEMPLATE_PREFIX:
            template_name = settings.FLAVOURS_TEMPLATE_PREFIX + template_name
        return template_name

    def load_template(self, template_name, template_dirs=None):
        template_name = self.prepare_template_name(template_name)
        for loader in self.template_source_loaders:
            try:
                return loader(template_name, template_dirs)
            except TemplateDoesNotExist:
                pass
        raise TemplateDoesNotExist("Tried %s" % template_name)

    def load_template_source(self, template_name, template_dirs=None):
        template_name = self.prepare_template_name(template_name)
        for loader in self.template_source_loaders:
            if hasattr(loader, 'load_template_source'):
                try:
                    return loader.load_template_source(template_name, template_dirs)
                except TemplateDoesNotExist:
                    pass
        raise TemplateDoesNotExist("Tried %s" % template_name)


class CachedLoader(BaseLoader):
    """
    Wrapper class that takes a list of template loaders as an argument and attempts
    to load templates from them in order, caching the result.
    To be used with django-mobile to cache different versions of template
    based on flavours (e.g. mobile)
    
    Based on https://github.com/anderser/django-mobile/blob/master/django_mobile/loader.py
    and the included django cached template loader:
    https://code.djangoproject.com/browser/django/tags/releases/1.3.1/django/template/loaders/cached.py
    
    """
    
    is_usable = True

    def __init__(self, loaders):
        self.template_cache = {}
        self._loaders = loaders
        self._cached_loaders = []
        

    @property
    def loaders(self):
        # Resolve loaders on demand to avoid circular imports
        if not self._cached_loaders:
            for loader in self._loaders:
                self._cached_loaders.append(find_template_loader(loader))
        return self._cached_loaders
    
    def prepare_template_name(self, template_name):
        
        flavour = get_flavour()
        
        #if None is given as flavour (default), then don't create path to flavour
        if flavour: 
            template_name = u'%s/%s' % (flavour, template_name)
            if settings.FLAVOURS_TEMPLATE_PREFIX:
                template_name = settings.FLAVOURS_TEMPLATE_PREFIX + template_name
        
        return template_name
    
    def find_template(self, name, dirs=None):
        """
        Find template based on flavour and fall back to
        no flavoured template if not found
        """
        
        flavoured_name = self.prepare_template_name(name)
        
        for loader in self.loaders:
            try:
                template, display_name = loader(flavoured_name, dirs)
                return (template, make_origin(display_name, loader, flavoured_name, dirs))
            except TemplateDoesNotExist:
                #if not flavoured template found, fallback to original/default 
                try:
                    template, display_name = loader(name, dirs)
                    return (template, make_origin(display_name, loader, name, dirs))
                except TemplateDoesNotExist:
                    pass
        raise TemplateDoesNotExist(name)

    def load_template(self, template_name, template_dirs=None):
        
        flavoured_template_name = self.prepare_template_name(template_name)
        key = flavoured_template_name
        
        if template_dirs:
            # If template directories were specified, use a hash to differentiate
            key = '-'.join([template_name, sha_constructor('|'.join(template_dirs)).hexdigest()])

        if key not in self.template_cache:
            print "Template key %s" % key, "NO HIT"
            template, origin = self.find_template(template_name, template_dirs)
            if not hasattr(template, 'render'):
                try:
                    template = get_template_from_string(template, origin, template_name)
                except TemplateDoesNotExist:
                    # If compiling the template we found raises TemplateDoesNotExist,
                    # back off to returning the source and display name for the template
                    # we were asked to load. This allows for correct identification (later)
                    # of the actual template that does not exist.
                    return template, origin
            self.template_cache[key] = template
        else:
            print "Template key %s" % key, "HIT"
        
        return self.template_cache[key], None

    def reset(self):
        "Empty the template cache."
        self.template_cache.clear()