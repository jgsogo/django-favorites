from django import template
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse
from django.template import Node
from django.template import TemplateSyntaxError
from django.template import Variable
from django.utils.translation import ugettext_lazy as _
from favorites.models import Favorite

register = template.Library()

@register.filter
def is_favorite(object, user):
    """
    Returns True, if object is already in user`s favorite list
    """
    if not user or not user.is_authenticated():
        return False
    return Favorite.objects.favorites_for_object(object, user).count()>0


@register.inclusion_tag("favorites/favorite_add_remove.html")
def add_remove_favorite(object, user):
    favorite = None
    content_type = ContentType.objects.get_for_model(object)
    if user.is_authenticated():
        favorite = Favorite.objects.favorites_for_object(object, user=user)
        if favorite:
            favorite = favorite[0]
        else:
            favorite = None
    count = Favorite.objects.favorites_for_object(object).count()
            
    return {"object_id": object.pk,
            "content_type_id": content_type.pk,
            "is_favorite":favorite,
            "count": count}
    
class FavoritesForObjectsNode(Node):
    def __init__(self, object_list, user, context_var):
        self.object_list = Variable(object_list)
        self.user = Variable(user)
        self.context_var = context_var

    def render(self, context):
        object_list = self.object_list.resolve(context)
        user = self.user.resolve(context)
        context[self.context_var] = Favorite.objects.favorites_for_objects(object_list, user)
        return ''
    
def do_favorites_for_objects(parser, token):
    """
    {% favorites_for_objects <object_list> <user> as <template_var> %}
    """
    bits = token.contents.split()
    if len(bits) != 5:
        raise TemplateSyntaxError(_('%s tag requires exactly four arguments') % bits[0])
    if bits[3] != 'as':
        raise TemplateSyntaxError(_("third argument to %s tag must be 'as'") % bits[0])
    return FavoritesForObjectsNode(bits[1], bits[2], bits[4])
register.tag('favorites_for_objects', do_favorites_for_objects)
    
class FavoriteEntryForItemNode(template.Node):
    def __init__(self, item, dictionary, context_var):
        self.item = item
        self.dictionary = dictionary
        self.context_var = context_var

    def render(self, context):
        try:
            dictionary = template.resolve_variable(self.dictionary, context)
            item = template.resolve_variable(self.item, context)
        except template.VariableDoesNotExist:
            return ''
        context[self.context_var] = dictionary.get("%s" % item.id, None)
        return ''

def do_favorite_entry_for_item(parser, token):
    """
    Given an object and a dictionary keyed with object ids - as
    returned by the ``favorites_for_objects`` template tags - 
    retrieves the value for the given object and
    stores it in a context variable, storing ``None`` if no value
    exists for the given object.

    Example usage::

        {% favorite_entry_for_item object from favorites_dict as favorite %}
    """
    bits = token.contents.split()
    if len(bits) != 6:
        raise template.TemplateSyntaxError("'%s' tag takes exactly five arguments" % bits[0])
    if bits[2] != 'from':
        raise template.TemplateSyntaxError("second argument to '%s' tag must be 'from'" % bits[0])
    if bits[4] != 'as':
        raise template.TemplateSyntaxError("fourth argument to '%s' tag must be 'as'" % bits[0])
    return FavoriteEntryForItemNode(bits[1], bits[3], bits[5])
register.tag('favorite_entry_for_item', do_favorite_entry_for_item)
