from django.contrib.admin import AdminSite
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from django.conf import settings

# from ledger.accounts import admin as ledger_admin
#from ledger.accounts.models import EmailUser, Document, Address, Profile
# from ledger.accounts.models import EmailUser
from ledger_api_client.ledger_models import EmailUserRO as EmailUser
from copy import deepcopy


class MooringLicensingAdminSite(AdminSite):
    site_header = 'Mooring Licensing Administration'
    site_title = 'Mooring Licensing Licensing'
    index_title = 'Mooring Licensing Licensing'

mooringlicensing_admin_site = MooringLicensingAdminSite(name='mooringlicensingadmin')

# admin.site.unregister(EmailUser) # because this base classAdmin alsready registered in ledger.accounts.admin
@admin.register(EmailUser)
class EmailUserAdmin(admin.ModelAdmin):
# class EmailUserAdmin(ledger_admin.EmailUserAdmin):
    """
    Overriding the EmailUserAdmin from ledger.accounts.admin, to remove is_superuser checkbox field on Admin page
    """

    def get_fieldsets(self, request, obj=None):
        """ Remove the is_superuser checkbox from the Admin page, if user is MooringLicensingAdmin and NOT superuser """
        fieldsets = super(UserAdmin, self).get_fieldsets(request, obj)
        #if not obj:
        #    return fieldsets

        if request.user.is_superuser:
            return fieldsets

        # User is not a superuser, remove is_superuser checkbox
        fieldsets = deepcopy(fieldsets)
        for fieldset in fieldsets:
            if 'is_superuser' in fieldset[1]['fields']:
                if type(fieldset[1]['fields']) == tuple :
                    fieldset[1]['fields'] = list(fieldset[1]['fields'])
                fieldset[1]['fields'].remove('is_superuser')
                break

        return fieldsets


