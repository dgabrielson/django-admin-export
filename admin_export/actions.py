"""
Admin actions.
"""
#######################################################################

from functools import partial

from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy

#######################################################################


def base_redirect_action(modeladmin, request, queryset, view_name, extra_query=None):
    """
    This is the base action.
    """
    url = reverse_lazy(view_name)
    selected = request.POST.getlist(admin.ACTION_CHECKBOX_NAME)
    qs_count = queryset.count()
    if qs_count != len(selected):
        # probably "select all" - but remember it may have a restricted "all"
        if qs_count == queryset.model.objects.all().count():
            query = "query=all"
        else:
            query = "query=" + "+".join(
                (str(e) for e in queryset.values_list("pk", flat=True))
            )
    else:
        query = "query=" + "+".join((str(e) for e in selected))
    ct = ContentType.objects.get_for_model(queryset.model)
    query += "&contenttype={0}".format(ct.pk)
    if extra_query:
        query += "&" + extra_query
    if query:
        url += "?" + query
    return HttpResponseRedirect(url)


#######################################################################


def spreadsheet_redirect_action(modeladmin, request, queryset, format):
    """
    Redirector for spreadsheet exports.
    Note that this is used as intermediate step for the various
    supported formats.
    """
    return base_redirect_action(
        modeladmin,
        request,
        queryset,
        "admin_export_spreadsheet",
        extra_query="format={0}".format(format),
    )


spreadsheet_redirect_action.short_description = "Export selected to spreadsheet"

#######################################################################

spreadsheet_actions = {}

for format in ["csv", "xlsx"]:  # consider also: odf, xls
    name = "export_redirect_spreadsheet_{0}".format(format)
    f = partial(spreadsheet_redirect_action, format=format)
    f.short_description = (
        spreadsheet_redirect_action.short_description + " ({0})".format(format)
    )
    f.__name__ = name
    spreadsheet_actions[name] = f
    globals()[name] = f


#######################################################################


def data_redirect_action(modeladmin, request, queryset, format):
    """
    Redirector for data exports.
    Note that this is used as intermediate step for the various
    supported formats.
    """
    return base_redirect_action(
        modeladmin,
        request,
        queryset,
        "admin_export_data",
        extra_query="format={0}".format(format),
    )


data_redirect_action.short_description = "Export selected to "

#######################################################################

data_actions = {}

for format in [
    "json",
    "xml",
]:  # consider also: yaml - but check if PyYAML is installed.
    name = "export_redirect_serializer_{0}".format(format)
    f = partial(data_redirect_action, format=format)
    f.short_description = data_redirect_action.short_description + " {0}".format(
        format.upper()
    )
    f.__name__ = name
    data_actions[name] = f
    globals()[name] = f


#######################################################################


def export_redirect_pdf(modeladmin, request, queryset):
    """
    Redirector for PDF export
    """
    return base_redirect_action(modeladmin, request, queryset, "admin_export_pdf")


export_redirect_pdf.short_description = "Export selected to PDF"


#######################################################################

SPREADSHEET_EXPORT_ACTIONS = list(spreadsheet_actions.values())
PDF_EXPORT_ACTIONS = [export_redirect_pdf]
CODE_EXPORT_ACTIONS = list(data_actions.values())

ALL_EXPORT_ACTIONS = (
    SPREADSHEET_EXPORT_ACTIONS + PDF_EXPORT_ACTIONS + CODE_EXPORT_ACTIONS
)

#######################################################################
