from django.db import models, connection
from django.contrib.contenttypes.models import ContentType


qn = connection.ops.quote_name


class FavoritesManagerMixin(object):
    """A Mixin to add a `favorite__favorite` column via extra"""
    def with_favorite_for(self, user, all=True):
        """ Adds a column favorite__favorite to the returned object, which
        indicates whether or not this item is a favorite for a user
        """
        Favorite = models.get_model('favorites', 'Favorite')
        content_type = ContentType.objects.get_for_model(self.model)
        pk_field = "%s.%s" % (qn(self.model._meta.db_table),
                              qn(self.model._meta.pk.column))

        favorite_sql = """(SELECT 1 FROM %(favorites_db_table)s 
WHERE %(favorites_db_table)s.object_id = %(pk_field)s and
      %(favorites_db_table)s.content_type_id = %(content_type)d and
      %(favorites_db_table)s.user_id = %(user_id)d)
""" % {'pk_field': pk_field, \
           'db_table': qn(self.model._meta.db_table), \
           'favorites_db_table': qn(Favorite._meta.db_table), \
           'user_id': user.pk, \
           'content_type': content_type.id, \
           }

        extras = {
            'select': {'favorite__favorite': favorite_sql},
            }

        if not all:
            extras['where'] = ['favorite__favorite == 1']

        return self.get_query_set().extra(**extras)


class FavoriteManager(models.Manager):
    """A Manager for Favorites"""
    def favorites_for_user(self, user):
        """ Returns Favorites for a specific user
        """
        return self.get_query_set().filter(user=user)

    def favorites_for_model(self, model, user=None):
        """Returns Favorites for a specific model"""
        content_type = ContentType.objects.get_for_model(model)
        qs = self.get_query_set().filter(content_type=content_type)
        if user:
            qs = qs.filter(user=user)
        return qs

    def favorites_for_object(self, obj, user=None):
        """Returns Favorites for a specific object"""
        content_type = ContentType.objects.get_for_model(type(obj))
        qs = self.get_query_set().filter(content_type=content_type, 
                                         object_id=obj.pk)
        if user:
            qs = qs.filter(user=user)

        return qs

    def favorites_for_objects(self, object_list, user=None):
        """Get a dictionary mapping object ids to favorite of votes for each object."""
        object_ids = [o.pk for o in object_list]
        if not object_ids:
            return {}

        content_type = ContentType.objects.get_for_model(object_list[0])

        qs = self.get_query_set().filter(content_type=content_type,
                                         object_id__in=object_ids)
        counters = qs.values('object_id').annotate(count=models.Count('object_id'))
        results = {}
        for c in counters:
            results.setdefault(c['object_id'], {})['count'] = c['count']
            results.setdefault(c['object_id'], {})['is_favorite'] = False
            results.setdefault(c['object_id'], {})['content_type_id'] = content_type.id
        if user and user.is_authenticated():
            qs = qs.filter(user=user)
            for f in qs:
                results.setdefault(f.object_id, {})['is_favorite'] = True

        return results

    def favorite_for_user(self, obj, user):
        """Returns the favorite, if exists for obj by user"""
        content_type = ContentType.objects.get_for_model(type(obj))
        return self.get_query_set().get(content_type=content_type,
                                    user=user, object_id=obj.pk)

    @classmethod
    def create_favorite(cls, content_object, user, folder=None):
        """create a :class:`favorites.models.Favorite` 
        
        :param content_object: object which is favorited.
        :param user: :class:`django.contrib.auth.models.User` for which the favorite is created.
        :param folder: :class:`favorites.models.Folder` where to put the favorite in. This should be
                        a folder owned by ``user``.
        :returns: a :class:`favorites.models.Favorite`.
        """
        content_type = ContentType.objects.get_for_model(type(content_object))
        Favorite = models.get_model('favorites', 'Favorite')
        favorite = Favorite(
            user=user,
            content_type=content_type,
            object_id=content_object.pk,
            content_object=content_object,
            folder = folder
            )
        favorite.save()
        return favorite
