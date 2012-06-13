from django.db import models, connection
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic

class FavoriteManager(models.Manager):
    """ A Manager for Favorites
    """
    def favorites_for_user(self, user):
        """ Returns Favorites for a specific user
        """
        return self.get_query_set().filter(user=user)

    def favorites_for_model(self, model, user=None):
        """ Returns Favorites for a specific model
        """
        content_type = ContentType.objects.get_for_model(model)
        qs = self.get_query_set().filter(content_type=content_type)
        if user:
            qs = qs.filter(user=user)
        return qs

    def favorites_for_object(self, obj, user=None):
        """ Returns Favorites for a specific object
        """
        content_type = ContentType.objects.get_for_model(type(obj))
        qs = self.get_query_set().filter(content_type=content_type,
                                         object_id=obj.pk)
        if user:
            qs = qs.filter(user=user)

        return qs

    def favorites_for_objects(self, object_list, user=None):
        """
        Get a dictionary mapping object ids to favorite
        of votes for each object.
        """
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
        """Returns the favorite, if exists for obj by user
        """
        content_type = ContentType.objects.get_for_model(type(obj))
        return self.get_query_set().get(content_type=content_type,
                                    user=user, object_id=obj.pk)

    @classmethod
    def create_favorite(cls, content_object, user, score=2.5):
        content_type = ContentType.objects.get_for_model(type(content_object))
        favorite = Favorite(
            user=user,
            content_type=content_type,
            object_id=content_object.pk,
            content_object=content_object,
            score=score
            )
        favorite.save()
        return favorite

    def average_score_for_object(self, obj):
        qs = self.favorites_for_object(obj).aggregate(models.Avg('score'))
        return qs.get('score__avg', None)

    def num_favorites_for_object(self, obj):
        return self.favorites_for_object(obj).count()

class Favorite(models.Model):
    user = models.ForeignKey(User)
    content_type = models.ForeignKey(ContentType)
    object_id = models.TextField(_('object ID'))
    content_object = generic.GenericForeignKey('content_type', 'object_id')

    score = models.FloatField(default=2.5)
    created_on = models.DateTimeField(auto_now_add=True, auto_now=True)

    objects = FavoriteManager()

    class Meta:
        verbose_name = _('favorite')
        verbose_name_plural = _('favorites')
        unique_together = (('user', 'content_type', 'object_id'),)

    def __unicode__(self):
        return "%s likes %s" % (self.user, self.content_object)

    def average_score(self):
        qs = Favorite.objects.filter(content_type=self.content_type, object_id=self.object_id).aggregate(models.Avg('score'))
        return qs.get('score__avg')

    def num_favorites(self):
        return Favorite.objects.filter(content_type=self.content_type, object_id=self.object_id).count()

@receiver(models.signals.post_delete)
def remove_favorites(sender, **kwargs):
    instance = kwargs.get('instance')
    Favorite.objects.favorites_for_object(instance).delete()
