
from django.dispatch import Signal

object_favorites_count = Signal(providing_args=['instance', 'count', 'rating'])
