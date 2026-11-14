"""Uploaded documents, served only to users who may see their application."""
import mimetypes
import os

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import FileResponse, Http404

from lwf.access import can_access_ticket
from lwf.models import AttachDocument


@staff_member_required
def protected_media(request, name):
    """Serve MEDIA_ROOT/<name> if it belongs to an application the user can access."""
    document = AttachDocument.objects.select_related('ticket').filter(file=name).first()
    ticket = document.ticket if document else None
    if ticket is None or not can_access_ticket(request.user, ticket):
        raise Http404
    path = os.path.realpath(os.path.join(settings.MEDIA_ROOT, name))
    if not path.startswith(os.path.realpath(settings.MEDIA_ROOT) + os.sep) or not os.path.isfile(path):
        raise Http404
    content_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'
    return FileResponse(open(path, 'rb'), content_type=content_type,
                        filename=os.path.basename(path), as_attachment=not content_type.startswith(('image/', 'application/pdf')))
