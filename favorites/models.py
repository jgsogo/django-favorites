from django.db import models, connection
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
    created_on = models.DateTimeField(auto_now_add=True)
    #: Boolean to know if this favorite is shared
    shared = models.BooleanField(default=False)

    #: see :class:`favorites.managers.FaovriteManger`
    objects = FavoriteManager()


    class Meta:
        verbose_name = _('favorite')
        verbose_name_plural = _('favorites')
        unique_together = (('user', 'content_type', 'object_id'),)

    def __unicode__(self):
        object_repr = unicode(self.content_object)
        return u"%s likes %s" % (self.user, object_repr)
