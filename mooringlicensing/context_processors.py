from mooringlicensing import settings
from ledger_api_client import utils as ledger_api_utils
import hashlib

def mooringlicensing_processor(request):

    web_url = request.META.get('HTTP_HOST', None)
    lt = ledger_api_utils.get_ledger_totals()

    checkouthash = None
    if 'payment_model' in request.session and 'payment_pk' in request.session:
        checkouthash =  hashlib.sha256(str(str(request.session["payment_model"])+str(request.session["payment_pk"])).encode('utf-8')).hexdigest()
        #check for ledger-api-client set checkouthash - if it is remove payment_model and payment_pk session variables and replace checkouthash
        if 'token_payment_session' in request.session:
            del request.session['payment_model']
            del request.session['payment_pk']

    if 'token_payment_session' in request.session:
        checkouthash =  hashlib.sha256(str(request.session["token_payment_session"]).encode('utf-8')).hexdigest()

    return {
        'public_url': web_url,
        'template_group': 'ria',
        'LEDGER_UI_URL': f'{settings.LEDGER_UI_URL}',
        'LEDGER_SYSTEM_ID': f'{settings.LEDGER_SYSTEM_ID}',
        'ledger_totals': lt,
        'checkouthash' : checkouthash,
        'GIT_COMMIT_DATE' : settings.GIT_COMMIT_DATE,
        'GIT_COMMIT_HASH' : settings.GIT_COMMIT_HASH,
        'QUEUE_DOMAIN' : settings.QUEUE_DOMAIN,
        'QUEUE_URL' : settings.QUEUE_URL,
        'QUEUE_ACTIVE_HOSTS' : settings.QUEUE_ACTIVE_HOSTS,
        'QUEUE_GROUP_NAME' : settings.QUEUE_GROUP_NAME,
        'management_commands_enabled': settings.ENABLE_MANAGEMENT_COMMANDS,
    }
