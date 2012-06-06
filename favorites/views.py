import urlparse

from django.views.generic.list_detail import object_list, object_detail
from django.shortcuts import get_object_or_404, redirect, render, render_to_response
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.template import RequestContext
from django.db.models import get_model
from django.http import (HttpResponse, HttpResponseNotFound, HttpResponseBadRequest,
                         HttpResponseForbidden)
from django.utils import simplejson
from django.core.urlresolvers import reverse

from utils import get_object_or_400_response
from models import Favorite, Folder
from favorites.forms import (FolderForm, UserFolderChoicesForm, ValidationForm,
                             HiddenFolderForm)

def _validate_next_parameter(request, next_url):
    parsed = urlparse.urlparse(next_url)
    if parsed and parsed.path:
        return parsed.path
    return None

# Taken from https://github.com/ericflo/django-avatar/blob/master/avatar/views.py
def _get_next(request):
    """
    The part that's the least straightforward about views in this module is how they
    determine their redirects after they have finished computation.

    In short, they will try and determine the next place to go in the following order:

    1. If there is a variable named ``next`` in the *POST* parameters, the view will
    redirect to that variable's value.
    2. If there is a variable named ``next`` in the *GET* parameters, the view will
    redirect to that variable's value.
    3. If Django can determine the previous page from the HTTP headers, the view will
    redirect to that previous page.
    """
    next_url = request.POST.get('next', request.GET.get('next', request.META.get('HTTP_REFERER', None)))
    if next_url:
        next_url = _validate_next_parameter(request, next_url)
    if not next_url:
        next_url = request.path
    return next_url


### FOLDER VIEWS ###########################################################

@login_required
def folder_list(request):
    """Lists user's folders

    :template favorites/folder_list.html: - ``object_list`` as list of user's folders
    """
    object_list = Folder.objects.filter(user=request.user)
    ctx = {'object_list': object_list}
    return render(request, 'favorites/folder_list.html', ctx)


@login_required
def folder_add(request):
    """Add a folder

    :template favorites/folder_add.html: - ``form`` is a :class:`favorites.forms.FolderForm`.
                                         - ``next_url`` value returned by :func:`favorites.views._get_next`
    """
    if request.method == 'POST':
        form = FolderForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            Folder(name=name, user=request.user).save()
            return redirect(_get_next(request))
    else:
        form = FolderForm()
        next_url = _get_next(request)
        ctx = {'form': form, 'next': next_url}
        return render(request, 'favorites/folder_add.html', ctx)


@login_required
def folder_update(request, object_id):
    """Update a folder. If current user doesn't own the folder, it returns 403 error.

    :param object_id: id of the :class:`favorites.models.Folder` that will be updated.

    :template favorites/folder_add.html: - ``form`` is a :class:`favorites.forms.FolderForm`.
                                         - ``next`` value returned by :func:`favorites.views._get_next`.
                                         - ``folder`` updated  :class:`favorites.models.Folder` object."""

    folder = get_object_or_404(Folder, pk=object_id)
    # check credentials
    if folder.user != request.user:
        return HttpResponseForbidden()

    if request.method == 'POST':
        form = FolderForm(request.POST)
        if form.is_valid():
            folder.name = form.cleaned_data['name']
            folder.save()
            return redirect(_get_next(request))
    else:
        form = FolderForm(initial={'name': folder.name})
        next_url = _get_next(request)
        ctx = {'form': form, 'next': next_url, 'folder': folder}
        return render(request, 'favorites/folder_update.html', ctx)


@login_required
def folder_delete(request, object_id):
    """Delete a folder with confirmation. If current user doesn't own the folder,
    it returns a 403 error.

    :param object_id: id of the :class:`favorites.models.Folder` to be deleted

    :template favorites/folder_delete.html: - ``folder`` :class:`favorites.models.Folder` to be deleted.
                                            - ``next`` value returned by :func:`favorites.views._get_next`."""
    folder = get_object_or_404(Folder, pk=object_id)
    # check credentials
    if request.user != folder.user:
        return HttpResponseForbidden()

    if request.method == 'POST':
        folder.delete()
        return redirect(_get_next(request))
    else:
        next_url = _get_next(request)
        ctx = {'folder': folder, 'next': next_url}
        return render(request, 'favorites/folder_delete.html', ctx)

### FAVORITE VIEWS #########################################################

### LIST


@login_required
def favorite_list(request):
    """Lists user's favorites

    :template favorites/favorite_list.html: - ``favorites`` list of user's :class:`favorites.models.Favorite`."""
    object_list = Favorite.objects.favorites_for_user(request.user)
    ctx = {'favorites': object_list}
    return render(request, 'favorites/favorite_list.html', ctx)


### ADD


@login_required
def favorite_add(request, app_label, object_name, object_id):  #FIXME factor
    """Renders a formular to get confirmation to favorite the
    object represented by `app_label`, `object_name` and `object_id`
    creation. It raise a 400 exception if there is not such object.
    If it's a `POST` creates the favorite object if there isn't
    a favorite already. If validation fails it renders an
    insightful error message. If the validation succeed the favorite is
    added and a redirection is returned. If the object is already a favorite 
    renders a message.

    :template favorites/favorite_already_favorite.html: - ``object`` object targeted by the favorite add operation.
                                                        - ``next`` value returned by :func:`favorites.views._get_next`.
                                                        - ``favorite`` :class:`favorites.models.Favorite`.

    :template favorites/favorite_add.html: - ``form`` :class:`favorites.forms.UserFolderChoicesForm` instance
                                           - ``object`` object targeted by the favorite add operation.
                                           - ``next`` value returned by :func:`favorites.views._get_next`.
    """

    # Is it a valid object ?
    instance_or_response = get_object_or_400_response(app_label, object_name, object_id)
    if isinstance(instance_or_response, HttpResponse):
        return instance_or_response  # the object is not found can be unknown
                                     # model or unknown object
    else:
        # it's a known object
        instance = instance_or_response
        favorites = Favorite.objects.favorites_for_object(instance, request.user)
        # is it already favorited by the user
        if favorites:
            # user already has this object as favorite
            favorite = favorites[0]
            ctx = {'object': instance, 'next': _get_next(request), 'favorite': favorite}
            return render(request, 'favorites/favorite_already_favorite.html', ctx)
        else:
            # init folder_choices for UserFolderChoicesForm validation or rendering
            query = Folder.objects.filter(user=request.user)
            folder_choices = query.order_by('name').values_list('pk', 'name')
            if request.method == 'POST':
                form = UserFolderChoicesForm(choices=folder_choices, data=request.POST)
                if form.is_valid():
                    folder_id = form.cleaned_data['folder_id']
                    if folder_id:
                        # form is valid hence the folder exists
                        folder = Folder.objects.get(pk=folder_id)
                    else:
                        folder = None
                    Favorite.objects.create_favorite(instance, request.user, folder)
                    return redirect(_get_next(request))
            else:  # GET
                form = UserFolderChoicesForm(choices=folder_choices)
            # if form is not valid or if it's a GET request
            ctx = {'form': form, 'object': instance, 'next':_get_next(request)}
            return render(request, 'favorites/favorite_add.html', ctx)


### DELETE

@login_required
def favorite_delete_for_object(request,
                               app_label,
                               object_name,
                               object_id):
    """Renders a formular to get confirmation to unfavorite the object
    represented by `app_label`, `object_name` and `object_id`. It raise a 404
    exception if there is no such object. If the action is successful the user
    is redirect using :func:`favorites.views._get_next`."""
    # Is it a valid object ?
    instance_or_response = get_object_or_400_response(app_label, object_name, object_id)
    if isinstance(instance_or_response, HttpResponse):
        # the object is not found can be unknown model or unknown object
        return instance_or_response
    else:
        instance = instance_or_response
        favorites = Favorite.objects.favorites_for_object(instance, request.user)
        if not favorites:
            # user has no favorite for this object
            return HttpResponseNotFound()
        else:
            favorite = favorites[0]
            return redirect(reverse('favorites:favorite_delete', kwargs={'object_id': favorite.pk}))


@login_required
def favorite_delete(request, object_id):
    """Renders a formular to get confirmation to unfavorite the object
    the favorite that has ``object_id`` as id. It raise a 404 if there
    is not such a favorite, a 403 error is returned if the favorite is not
    owned by current user. If the action is successful the user
    is redirect using :func:`favorites.views._get_next`.

    :template favorites/favorite_delete.html: - ``form`` :class:`favorites.forms.Validation` instance.
                                              - ``favorite`` :class:`favorites.models.Favorite` to be deleted.
                                              - ``next`` value returned by :func:`favorites.views._get_next`."""
    favorite = get_object_or_404(Favorite, pk=object_id)
    # check credentials
    if not request.user == favorite.user:
        return HttpResponseForbidden()
    else:
        if request.method == 'POST':
            form = ValidationForm(request.POST)
            if form.is_valid():
                favorite.delete()
                return redirect(_get_next(request))
        else:
            form = ValidationForm()
        # if form is not valid or if it's a GET request
        ctx = {'form': form, 'favorite': favorite, 'next': _get_next(request)}
        return render(request, 'favorites/favorite_delete.html', ctx)


### MOVE


@login_required
def favorite_move(request, object_id):
    """Renders a formular to move a favorite to another folder. If the action is successful the user
    is redirect using :func:`favorites.views._get_next`.

    :template favorites/favorite_move.html: - ``favorite`` :class:`favorites.models.Favorite` instance target of the operation.
                                            - ``next`` value returned by :func:`favorites.views._get_next`.
                                            - ``form`` :class:`favorites.forms.UserFolderChoicesForm` instance.
    """
    favorite = get_object_or_404(Favorite, pk=object_id)
    # check credentials
    if not favorite.user == request.user:
        return HttpResponseForbidden()
    else:
        # init folder choices for form
        folder_choices = Folder.objects.filter(user=request.user).order_by('name').values_list('pk', 'name')

        if request.method == 'POST':
            form = UserFolderChoicesForm(choices=folder_choices, data=request.POST)
            if form.is_valid():
                folder_id = form.cleaned_data['folder_id']
                if folder_id == '':
                    folder = None
                else:
                    folder = get_object_or_404(Folder, pk=folder_id)
                favorite.folder = folder
                favorite.save()
                return redirect(_get_next(request))
        else:
            folder_id = favorite.folder.pk if favorite.folder else ''
            form = UserFolderChoicesForm(choices=folder_choices, initial={'folder_id': folder_id})
        # form is not valid or it's a GET request
        ctx = {'favorite': favorite, 'next': _get_next(request), 'form': form}
        return render(request, 'favorites/favorite_move.html', ctx)


@login_required
def favorite_move_to_folder(request, favorite_id, folder_id):
    """moves a favorite to a folder provided as a get parameter with confirmation. 
    If the action is successful the user is redirect using :func:`favorites.views._get_next`.
    
    :template favorites/favorite_move_to_folder.html: - ``form`` :class:`favorites.forms.HiddenFolderForm` instance.
                                                      - ``favorite`` :class:`favorites.models.Favorite` instance.
                                                      - ``folder`` :class:`favorites.models.Folder` instance.
                                                      - ``next`` value returned by :func:`favorites.views._get_next`."""
    favorite = get_object_or_404(Favorite, pk=favorite_id)
    # check credentials on favorite
    if request.user != favorite.user:
        return HttpResponseForbidden()
    # fetch folder
    if folder_id:
        folder = get_object_or_404(Folder, pk=folder_id)
        # check credentials
        if request.user != folder.user:
            return HttpResponseForbidden()
        folder_pk = folder.pk
    else:
        folder = None
        folder_pk = '' # special case for root folder

    form = HiddenFolderForm(initial={'folder_id': folder_pk})
    next_url = _get_next(request)
    ctx = {
    'form': form,
    'favorite': favorite,
    'folder': folder,
    'next': next_url
}
    return render(request, 'favorites/favorite_move_to_folder.html', ctx)


@login_required
def favorite_toggle_share(request, favorite_id):
    """Confirm before submiting the toggle share action. If the action is successful 
    the user is redirect using :func:`favorites.views._get_next`.

    :template favorites/favorite_toggle_share.html: - ``favorite`` :class:`favorites.models.Favorite` instance."""
    favorite = get_object_or_404(Favorite, pk=favorite_id)
    # check crendentials
    if request.user != favorite.user:
        return HttpResponseForbidden()
    else:
        if request.method == 'POST':
            form = ValidationForm(data=request.POST)
            if form.is_valid():
                favorite.shared = False if favorite.shared else True  # toggle
                favorite.save()
                return redirect(_get_next(request))
        else:
            form = ValidationForm()
        # form is not valid or it's a GET request
        ctx = {'favorite': favorite}
        return render(request, 'favorites/favorite_toggle_share.html', ctx)


@login_required
def favorite_content_type_and_folder_list(request, app_label, object_name, folder_id=None):
    """
    Retrieve favorites for a user by content_type.

    The optional folder_id parameter will be used to filter the favorites, if
    passed.

    :template favorites/favorite_content_type_list.html: - ``app_label`` Generic Foreign Key parameter.
                                                         - ``object_name`` Generic Foreign Key parameter.

                                                         - ``favorites`` :class:`favorites.models.Favorites`

    :template favorites/favorite_{{app_label}}_{{object_name}}_list.html: same as above

    :template favorites/favorite_{{app_label}}_{{object_name}}_by_folder_list.html: - same as above and 
                                                                                    - ``folder`` :class:`favorites.models.Folder` instance."""
    model = get_model(app_label, object_name)
    if model is None:
        return HttpResponseBadRequest()
    content_type = ContentType.objects.get_for_model(model)

    filters = {"content_type":content_type, "user":request.user}
    templates = []
    context_data = {
        'app_label': app_label,
        'object_name': object_name,
        'folder': None
    }

    if folder_id:
        folder = get_object_or_404(Folder, pk=folder_id)
        if not folder.user == request.user:
            return HttpResponseForbidden()
        filters["folder"] = folder
        context_data["folder"] = folder
        dynamic_template = 'favorites/favorite_%s_%s_by_folder_list.html' \
                                                      % (app_label, object_name)
        templates.append(dynamic_template)

    favorites = Favorite.objects.filter(**filters)
    context_data["favorites"] = favorites

    # Set content_type specific and default templates
    dynamic_template = 'favorites/favorite_%s_%s_list.html' % (app_label,
                                                                    object_name)
    templates.append(dynamic_template)
    # Default
    templates.append('favorites/favorite_content_type_list.html')
    return render(request, templates, context_data)
