from django.db import models, connection
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic

from favorites.managers import FavoriteManager


class Folder(models.Model):
    """Persistent folder object bound to an a :class:`django.contrib.auth.models.User`."""
    #: user that owns this folder
    user = models.ForeignKey(User)
    #: name of the folder
    name = models.CharField(max_length=100)

    def __unicode__(self):
        return self.name


class Favorite(models.Model):
    """Persistent favorite object bound to a user, folder and object"""
    #: user that owns this favorite
    user = models.ForeignKey(User)

    #: Favorited object type (part of the generic foreign key)
    content_type = models.ForeignKey(ContentType)
    #: id of the object favorited (part of the generic foreign key)
    object_id = models.PositiveIntegerField()
    #: Favorited object. Use this attribute to access the favorited object.
    content_object = generic.GenericForeignKey('content_type', 'object_id')

    #: :class:`favorites.models.Folder`` in which the favorite can be found.
    folder = models.ForeignKey(Folder, null=True, blank=True)
    #: Date of creation
    created_on = models.DateTimeField(auto_now_add=True, auto_now=True)
    #: Boolean to know if this favorite is shared
    shared = models.BooleanField(default=False)

    #: Score given for this user to this favorite
    score = models.FloatField(default=2.5)

    #: see :class:`favorites.managers.FaovriteManger`
    objects = FavoriteManager()


    class Meta:
        verbose_name = _('favorite')
        verbose_name_plural = _('favorites')
        unique_together = (('user', 'content_type', 'object_id'),)

    def __unicode__(self):
        object_repr = unicode(self.content_object)
        return u"%s likes %s" % (self.user, object_repr)

    def average_score(self):
        qs = Favorite.objects.filter(content_type=self.content_type, object_id=self.object_id).aggregate(models.Avg('score'))
        return qs.get('score__avg')

    def num_favorites(self):
        return Favorite.objects.filter(content_type=self.content_type, object_id=self.object_id).count()


""" Stuff related to signals """
from favorites.signals import object_favorites_count

@receiver(models.signals.post_delete)
def remove_favorites(sender, **kwargs):
    instance = kwargs.get('instance')
    try:
        Favorite.objects.favorites_for_object(instance).delete()
    except:
        pass

@receiver(models.signals.post_save, sender=Favorite)
def on_new_favorite(sender, instance, created, **kwargs):
    if created:
        count = instance.num_favorites()
        rating = instance.average_score()
        object_favorites_count.send(sender=instance.content_object.__class__, instance=instance.content_object, count=count, rating=rating)
