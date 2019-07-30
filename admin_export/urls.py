"""
Url patterns for admin exports.
"""
#######################
from __future__ import print_function, unicode_literals

from admin_export.views import ExportPDF, ExportSerializer, ExportSpreadsheet
from django.conf.urls import url
from django.contrib.admin.sites import site

#######################
#######################################################################


#######################################################################

admin_export_spreadsheet = site.admin_view(ExportSpreadsheet.as_view())
admin_export_pdf = site.admin_view(ExportPDF.as_view())
admin_export_data = site.admin_view(ExportSerializer.as_view())

#######################################################################

urlpatterns = [
    url(r"^spreadsheet/$", admin_export_spreadsheet, name="admin_export_spreadsheet"),
    url(r"^pdf/$", admin_export_pdf, name="admin_export_pdf"),
    url(r"^data/$", admin_export_data, name="admin_export_data"),
]


#######################################################################

# Consider placing this or some variation in the file which includes this
# one.  Otherwise exporters can be enable in individual model admins
# appropriately (by setting/extending the ``actions`` class attribute).

# Current action names are:
#   SPREADSHEET_EXPORT_ACTIONS:
#         * export_redirect_spreadsheet_csv
#         * export_redirect_spreadsheet_xlsx
#   PDF_EXPORT_ACTIONS:
#         * export_redirect_pdf
#   DATA_EXPORT_ACTIONS
#         * export_redirect_data_xml
#         * export_redirect_data_json

# Enable export actions globaly
# from django.contrib.admin.sites import site
# from admin_export.actions import ALL_EXPORT_ACTIONS
# for action in ALL_EXPORT_ACTIONS:
#     site.add_action(action, action.__name__)

#######################################################################
