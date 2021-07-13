from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.utils.http import urlquote_plus

import re
import datetime

from django.http import HttpResponseRedirect
from django.utils import timezone
#from mooringlicensing.components.bookings.models import ApplicationFee
from reversion.middleware  import RevisionMiddleware
from reversion.views import _request_creates_revision
from mooringlicensing.components.main.utils import add_cache_control

CHECKOUT_PATH = re.compile('^/ledger/checkout/checkout')

class FirstTimeNagScreenMiddleware(object):
    def process_request(self, request):
        #print ("FirstTimeNagScreenMiddleware: REQUEST SESSION")
        if request.user.is_authenticated() and request.method == 'GET' and 'api' not in request.path and 'admin' not in request.path:
            if (not request.user.first_name or not request.user.last_name):
                path_ft = reverse('first_time')
                path_logout = reverse('accounts:logout')
                if request.path not in (path_ft, path_logout):
                    #response = add_cache_control(redirect(reverse('first_time')+"?next="+urlquote_plus(request.get_full_path())))
                    return add_cache_control(redirect(reverse('first_time')+"?next="+urlquote_plus(request.get_full_path())))

class CacheControlMiddleware(object):
    def process_response(self, request, response):
        return add_cache_control(response)

    #def __init__(self, get_response):
    #    self.get_response = get_response

    #def __call__(self, request):
    #    response = self.get_response(request)
    #    #print(response.__dict__)

    #    return response

#class BookingTimerMiddleware(object):
#    def process_request(self, request):
#        #print ("BookingTimerMiddleware: REQUEST SESSION")
#        #print request.session['ps_booking']
#        if 'cols_app_invoice' in request.session:
#            #print ("BOOKING SESSION : "+str(request.session['ps_booking']))
#            try:
#                application_fee = ApplicationFee.objects.get(pk=request.session['cols_app_invoice'])
#            except:
#                # no idea what object is in self.request.session['ps_booking'], ditch it
#                del request.session['cols_app_invoice']
#                return
#            if application_fee.payment_type != ApplicationFee.PAYMENT_TYPE_TEMPORARY:
#                # booking in the session is not a temporary type, ditch it
#                del request.session['cols_app_invoice']
#        return

class RevisionOverrideMiddleware(RevisionMiddleware):

    """
        Wraps the entire request in a revision.

        override venv/lib/python2.7/site-packages/reversion/middleware.py
    """

	# exclude ledger payments/checkout from revision - hack to overcome basket (lagging status) issue/conflict with reversion
    def request_creates_revision(self, request):
        return _request_creates_revision(request) and 'checkout' not in request.get_full_path()
