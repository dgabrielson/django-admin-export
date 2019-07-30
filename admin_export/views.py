"""
Views for admin exports.
"""
#######################################################################

import mimetypes

from django.contrib.auth import get_permission_codename
from django.contrib.contenttypes.models import ContentType
from django.core import serializers
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.template import TemplateDoesNotExist, loader
from django.template.response import TemplateResponse
from django.views.generic.list import ListView
from latex.djangoviews import LaTeXListView
from spreadsheet import sheetWriter

from .utils import default_latex_template, resolve_lookup, titlize

#######################################################################


class ExportMixin(object):
    """
    Mixin for common export code.

    This provides a default mechanism for specifying fields.
    """

    export_fields = None  # or a list of strings; field names for export.
    template_base = "admin"  # /app_label/model/export will be added.
    export_fields_template_name = "export_fields.txt"

    # allow post to this view -- admin actions.
    # def post(self, *args, **kwargs):
    #    return self.get(*args, **kwargs)
    def get_contenttype(self):
        """
        Get the content type of the model.
        """
        contenttype_pk = self.request.GET.get("contenttype", None)
        if contenttype_pk is None:
            raise ImproperlyConfigured("Export views require a contenttype paramter")
        ct = ContentType.objects.get(pk=contenttype_pk)
        return ct

    def get_model(self):
        """
        Get the model we are working with
        """
        return self.get_contenttype().model_class()

    def get_export_fields_template_name(self):
        """
        Return the template name for export fields.
        """
        ct = self.get_contenttype()
        name = "{0}/{1}/{2}".format(
            ct.app_label, ct.model, self.export_fields_template_name
        )
        if self.template_base:
            name = self.template_base + "/" + name
        return name

    def get_export_fields(self):
        """
        Get the fields to export.
        Custom exporters should either provide an export_field list
        on a subclass or override this method.
        """
        # pre defined field list:
        if self.export_fields:
            return self.export_fields

        # field list from template:
        try:
            t = loader.get_template(self.get_export_fields_template_name())
        except TemplateDoesNotExist:
            pass
        else:
            self.export_fields = t.render({}).strip().split("\n")
            return self.export_fields

        # introspection!
        model_class = self.get_model()
        return [f.name for f in model_class._meta.fields]

    def get_field_labels(self):
        """
        Determine the field labels for what is getting exported.
        """
        model_class = self.get_model()
        fields = self.get_export_fields()
        return [titlize(model_class, f) for f in fields]

    def get_template_names(self):
        """
        Get the template name.
        Note: descendant classes should call this but add their own
        extensions.
        Also note that these templates only make sense for certain
        types of export; and that if present the ``export_fields`` will
        be ignored.
        If no templates exist; then ``get_export_fields()`` will be called.
        """
        ct = self.get_contenttype()
        name = "{0}/{1}/export".format(ct.app_label, ct.model)
        if self.template_base:
            name = self.template_base + "/" + name
        return [name]

    def security_filter(self, queryset):
        """
        Check to ensure that it's reasonable to release data contained
        in this queryset.
        """
        if not self.request.user:
            return queryset.empty()
        model = self.get_model()
        codename = get_permission_codename("change", model._meta)
        permname = "%s.%s" % (model._meta.app_label, codename)
        if self.request.user.has_perm(permname):
            return queryset
        # adaptively attempt to use django guardian.
        try:
            from guardian.shortcuts import get_objects_for_user
        except ImportError:
            pass
        else:
            user_qs = get_objects_for_user(self.request.user, permname)
            user_pk_list = user_qs.values_list("pk", flat=True)
            return queryset.filter(pk__in=user_pk_list)
        return queryset.none()

    def get_queryset(self):
        """
        Get the actual queryset.
        """
        model = self.get_model()
        qs = model.objects.all()
        if "pk" in self.request.GET:
            selected = self.request.GET.getlist("pk")
            qs = qs.filter(pk__in=selected)
        elif "query" in self.request.GET:
            query = self.request.GET.get("query")
            if query != "all":
                selected = query.split()
                qs = qs.filter(pk__in=selected)
        else:
            qs = qs.none()
        qs = self.security_filter(qs)
        return qs

    def is_template_export(self, template):
        """
        Called to see if this will be rendered via a template; or via
        fields.
        """
        if template is None:
            # this method is often called from ``get_template_names()``
            # so be wary of recursion.
            template = self.get_template_names()

        if isinstance(template, (list, tuple)):
            try:
                return loader.select_template(template)
            except TemplateDoesNotExist:
                pass
        elif isinstance(template, six.string_types):
            try:
                return loader.get_template(template)
            except TemplateDoesNotExist:
                pass
        # will not be exported via a template.
        return None


#######################################################################


class ExportSpreadsheet(ExportMixin, ListView):
    """
    Spreadsheet exporter.
    """

    include_headers = True
    as_attachment = False

    def __init__(self, *args, **kwargs):
        self.render_via_template = False
        return super(ExportSpreadsheet, self).__init__(*args, **kwargs)

    def get_format(self):
        """
        Get the format for the spreadsheet.
        """
        format = self.request.GET.get("format", None)
        if format is None:
            raise ImproperlyConfigured(
                "Export spreadsheet views require a format paramter"
            )
        return format

    def is_template_export(self, template):
        result = super(ExportSpreadsheet, self).is_template_export(template)
        if result is not None:
            self.render_via_template = True

    def get_template_names(self):
        """
        Get the template name.
        Note: descendant classes should call this but add their own
        extensions.
        Templates make sense for, e.g., CSV or tab-delimted files;
        but not for binary spreadsheet formats.
        """
        template_list = super(ExportSpreadsheet, self).get_template_names()
        format = self.get_format()
        template_list = [t + "." + format for t in template_list]
        template = self.is_template_export(template_list)
        if template is not None:
            # return pre-rendered template
            return template
        return template_list

    def get_filename(self):
        """
        Return a suggested filename for the export.
        """
        ct = self.get_contenttype()
        return "{1}_list.{2}".format(ct.app_label, ct.model, self.get_format())

    def get_as_attachment(self):
        return self.as_attachment

    def _augment_response(self, response, filename=None):
        """
        Augment the response object with extra headers, e.g.,
        * Filename
        * Content-Disposition
        """
        if filename is None:
            filename = self.get_filename()
        response["Filename"] = filename  # IE needs this
        if self.get_as_attachment():
            attachment = "attachment; "
        else:
            attachment = ""
        response["Content-Disposition"] = "{0}filename={1}".format(attachment, filename)
        content_type, encoding = mimetypes.guess_type(filename)
        response["Content-Type"] = content_type
        return response

    def export_spreadsheet_response(self):
        """
        Actually do the spreadsheet export
        """
        fields = self.get_export_fields()
        # Future: maybe introspect for field verbose names?
        headers = self.get_field_labels()
        if self.include_headers:
            data = [headers]
        else:
            data = []
        for obj in self.get_queryset():
            data.append([resolve_lookup(obj, f) for f in fields])
        # now, construct the data stream.
        stream = sheetWriter(data, self.get_format())
        response = HttpResponse(stream)
        return response

    def render_to_response(self, context, **response_kwargs):
        """
        Returns a response, using the `response_class` for this
        view, with a template rendered with the given context.

        If any keyword arguments are provided, they will be
        passed to the constructor of the response class.
        """
        self.get_template_names()
        if self.render_via_template:
            # may need to augment the response appropriately.
            response = super(ExportSpreadsheet, self).render_to_response(
                context, **response_kwargs
            )
        else:
            response = self.export_spreadsheet_response()

        return self._augment_response(response)


#######################################################################


class ExportPDF(ExportMixin, LaTeXListView):
    """
    PDF exporter.
    """

    as_attachment = False

    def get_filename(self, doc=None):
        """
        Return a suggested filename for the export.
        """
        ct = self.get_contenttype()
        filename = "{1}_list.pdf".format(ct.app_label, ct.model)
        return self.fix_filename_extension(filename)

    def get_template_names(self):
        """
        Get the template name.
        Note: descendant classes should call this but add their own
        extensions.
        """
        template_list = super(ExportPDF, self).get_template_names()
        template_list = [t + ".tex" for t in template_list]
        # this will pre-render an existing template; or return None
        template = self.is_template_export(template_list)
        if template is None:
            headers = self.get_field_labels()
            fields = self.get_export_fields()
            # Note: This is a compiled Django template.
            return default_latex_template(headers, fields)
        return template


#######################################################################


class ExportSerializer(ExportMixin, ListView):
    """
    Django core serializer exporter.
    """

    as_attachment = True

    def get_format(self):
        format = self.request.GET.get("format", None)
        if format is None:
            raise ImproperlyConfigured(
                "Export serializer views require a format paramter"
            )
        return format

    def get_filename(self):
        """
        Return a suggested filename for the export.
        """
        ct = self.get_contenttype()
        return "{1}_list.{2}".format(ct.app_label, ct.model, self.get_format())

    def get_as_attachment(self):
        return self.as_attachment

    def _augment_response(self, response, filename=None):
        """
        Augment the response object with extra headers, e.g.,
        * Filename
        * Content-Disposition
        """
        if filename is None:
            filename = self.get_filename()
        response["Filename"] = filename  # IE needs this
        if self.get_as_attachment():
            attachment = "attachment; "
        else:
            attachment = ""
        response["Content-Disposition"] = "{0}filename={1}".format(attachment, filename)
        return response

    def render_to_response(self, *args, **kwargs):
        """
        Return the serialized queryset.
        """
        filename = self.get_filename()
        content_type, encoding = mimetypes.guess_type(filename)
        response = HttpResponse(content_type=content_type)
        queryset = self.get_queryset()
        format = self.get_format()
        serializers.serialize(format, queryset, stream=response)
        return self._augment_response(response, filename=filename)


#####################################################################
