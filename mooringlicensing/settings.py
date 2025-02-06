import json
from django.core.exceptions import ImproperlyConfigured

import os
from confy import env
import confy
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
confy.read_environment_file(BASE_DIR+"/.env")
os.environ.setdefault("BASE_DIR", BASE_DIR)

from ledger_api_client.settings_base import *

ROOT_URLCONF = 'mooringlicensing.urls'
SITE_ID = 1
DEPT_DOMAINS = env('DEPT_DOMAINS', ['dpaw.wa.gov.au', 'dbca.wa.gov.au'])
SYSTEM_MAINTENANCE_WARNING = env('SYSTEM_MAINTENANCE_WARNING', 24) # hours
DISABLE_EMAIL = env('DISABLE_EMAIL', False)
SHOW_TESTS_URL = env('SHOW_TESTS_URL', False)
SHOW_DEBUG_TOOLBAR = env('SHOW_DEBUG_TOOLBAR', False)
SHOW_API_ROOT = env('SHOW_API_ROOT', False)

#Settings for rounding application fee items
ROUND_FEE_ITEMS = env('ROUND_FEE_ITEMS', False)

if SHOW_DEBUG_TOOLBAR:

    def show_toolbar(request):
        return True

    MIDDLEWARE_CLASSES += [
        'debug_toolbar.middleware.DebugToolbarMiddleware',
    ]
    INSTALLED_APPS += (
        'debug_toolbar',
    )
    INTERNAL_IPS = ('127.0.0.1', 'localhost')

    # this dict removes check to dtermine if toolbar should display --> works for rks docker container
    DEBUG_TOOLBAR_CONFIG = {
        "SHOW_TOOLBAR_CALLBACK" : show_toolbar,
        'INTERCEPT_REDIRECTS': False,
    }

STATIC_URL = '/static/'


INSTALLED_APPS += [
    'webtemplate_dbca',
    'smart_selects',
    'reversion',
    'reversion_compare',
    'bootstrap3',
    'mooringlicensing',
    'mooringlicensing.components.main',
    'mooringlicensing.components.emails',
    'mooringlicensing.components.users',
    'mooringlicensing.components.proposals',
    'mooringlicensing.components.approvals',
    'mooringlicensing.components.compliances',
    'mooringlicensing.components.payments_ml',
    'rest_framework',
    'rest_framework_datatables',
    'reset_migrations',
    'ledger_api_client',
    'appmonitor_client',
    'crispy_bootstrap5',
    'crispy_forms',
]

ADD_REVERSION_ADMIN=True

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
        'rest_framework_datatables.renderers.DatatablesRenderer',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
}

MIDDLEWARE_CLASSES += [
    'mooringlicensing.middleware.FirstTimeNagScreenMiddleware',
    'mooringlicensing.middleware.PaymentSessionMiddleware',
    'mooringlicensing.middleware.RevisionOverrideMiddleware',
    'mooringlicensing.middleware.CacheControlMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
]
MIDDLEWARE = MIDDLEWARE_CLASSES
WSGI_APPLICATION = "mooringlicensing.wsgi.application"

TEMPLATES[0]['DIRS'].append(os.path.join(BASE_DIR, 'mooringlicensing', 'templates'))
TEMPLATES[0]['OPTIONS']['context_processors'].append('mooringlicensing.context_processors.mooringlicensing_processor')
del BOOTSTRAP3['css_url']

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': os.path.join(BASE_DIR, 'mooringlicensing', 'cache'),
    }
}
STATIC_ROOT=os.path.join(BASE_DIR, 'staticfiles_ml')
DEBUG_ENV = env('DEBUG', False)
if DEBUG_ENV:
    STATICFILES_DIRS.append(os.path.join(os.path.join(BASE_DIR, 'mooringlicensing', 'static')))
DEV_STATIC = env('DEV_STATIC',False)
DEV_STATIC_URL = env('DEV_STATIC_URL')
if DEV_STATIC and not DEV_STATIC_URL:
    raise ImproperlyConfigured('If running in DEV_STATIC, DEV_STATIC_URL has to be set')
DATA_UPLOAD_MAX_NUMBER_FIELDS = None
DEV_APP_BUILD_URL = env('DEV_APP_BUILD_URL')  # URL of the Dev app.js served by webpack & express

RAND_HASH = ''
if os.path.isdir(BASE_DIR+'/.git/') is True:
    RAND_HASH = os.popen('cd  '+BASE_DIR+' ; git log -1 --format=%H').read()
if not len(RAND_HASH):
    RAND_HASH = os.popen('cat /app/rand_hash').read()
if len(RAND_HASH) == 0:
    print ("ERROR: No rand hash provided")

# Department details
SYSTEM_NAME = env('SYSTEM_NAME', 'Mooring Licensing')
SYSTEM_NAME_SHORT = env('SYSTEM_NAME_SHORT', 'ML')
SITE_PREFIX = env('SITE_PREFIX', '')
SITE_DOMAIN = env('SITE_DOMAIN', '')
SUPPORT_EMAIL = env('SUPPORT_EMAIL', 'mooringlicensing@' + SITE_DOMAIN).lower()
DEP_URL = env('DEP_URL','www.' + SITE_DOMAIN)
DEP_PHONE = env('DEP_PHONE','(08) 9219 9978')
DEP_PHONE_SUPPORT = env('DEP_PHONE_SUPPORT','(08) 9219 9000')
DEP_FAX = env('DEP_FAX','(08) 9423 8242')
DEP_POSTAL = env('DEP_POSTAL','Locked Bag 104, Bentley Delivery Centre, Western Australia 6983')
DEP_NAME = env('DEP_NAME','Department of Biodiversity, Conservation and Attractions')
DEP_NAME_SHORT = env('DEP_NAME_SHORT','DBCA')
RIA_NAME = env('RIA_NAME', 'Rottnest Island Authority (RIA)')
SITE_URL = env('SITE_URL', 'https://' + SITE_PREFIX + '.' + SITE_DOMAIN)
PUBLIC_URL=env('PUBLIC_URL', SITE_URL)
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', 'no-reply@' + SITE_DOMAIN).lower()
MEDIA_APP_DIR = env('MEDIA_APP_DIR', 'mooringlicensing')
CRON_RUN_AT_TIMES = env('CRON_RUN_AT_TIMES', '04:05')
CRON_EMAIL = env('CRON_EMAIL', 'cron@' + SITE_DOMAIN).lower()
CRON_NOTIFICATION_EMAIL = env('CRON_NOTIFICATION_EMAIL', NOTIFICATION_EMAIL).lower()
EMAIL_FROM = DEFAULT_FROM_EMAIL
os.environ['LEDGER_PRODUCT_CUSTOM_FIELDS'] = "('ledger_description','quantity','price_incl_tax','price_excl_tax','oracle_code')"

SYSTEM_EMAIL=env('SYSTEM_EMAIL','ledger@dbca.wa.gov.au')

ADMIN_GROUP = env('ADMIN_GROUP', 'Mooring Licensing - Admin')

BASE_URL=env('BASE_URL')

CONSOLE_EMAIL_BACKEND = env('CONSOLE_EMAIL_BACKEND', False)
if CONSOLE_EMAIL_BACKEND:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

OSCAR_BASKET_COOKIE_OPEN = 'mooringlicensing_basket'
LEDGER_SYSTEM_ID = env('PAYMENT_INTERFACE_SYSTEM_PROJECT_CODE', 'PAYMENT_INTERFACE_SYSTEM_PROJECT_CODE not configured')
PAYMENT_SYSTEM_ID = LEDGER_SYSTEM_ID.replace('0', 'S')
MOORING_BOOKINGS_API_KEY=env('MOORING_BOOKINGS_API_KEY')
MOORING_BOOKINGS_API_URL=env('MOORING_BOOKINGS_API_URL')

PROPOSAL_TYPE_NEW = 'new'
PROPOSAL_TYPE_RENEWAL = 'renewal'
PROPOSAL_TYPE_AMENDMENT = 'amendment'
PROPOSAL_TYPE_SWAP_MOORINGS = 'swap_moorings'
PROPOSAL_TYPES_FOR_FEE_ITEM = [
    (PROPOSAL_TYPE_NEW, 'New Application'),
    (PROPOSAL_TYPE_AMENDMENT, 'Amendment'),
    (PROPOSAL_TYPE_RENEWAL, 'Renewal'),
    (PROPOSAL_TYPE_SWAP_MOORINGS, 'Swap Moorings'),
]
PROPOSAL_TYPES = [
    {
        'code': PROPOSAL_TYPE_NEW,
        'description': 'New Application',
    },
    {
        'code': PROPOSAL_TYPE_AMENDMENT,
        'description': 'Amendment',
    },
    {
        'code': PROPOSAL_TYPE_RENEWAL,
        'description': 'Renewal',
    },
    {
        'code': PROPOSAL_TYPE_SWAP_MOORINGS,
        'description': 'Swap Moorings',
    },
]

HTTP_HOST_FOR_TEST = 'localhost:8071'
APPLICATION_TYPE_DCV_PERMIT = {
    'code': 'dcvp',
    'description': 'DCV Permit',
    'fee_by_fee_constructor': True,
}
APPLICATION_TYPE_DCV_ADMISSION = {
    'code': 'dcv',
    'description': 'DCV Admission',
    'fee_by_fee_constructor': True,
}
APPLICATION_TYPE_REPLACEMENT_STICKER = {
    'code': 'replacement_sticker',
    'description': 'Replacement sticker fees',
    'fee_by_fee_constructor': False,
}
APPLICATION_TYPE_MOORING_SWAP = {
    'code': 'mooring_swap',
    'description': 'Mooring swap fees',
    'fee_by_fee_constructor': False,
}
APPLICATION_TYPES = [
    APPLICATION_TYPE_DCV_PERMIT,
    APPLICATION_TYPE_DCV_ADMISSION,
    APPLICATION_TYPE_REPLACEMENT_STICKER,
    APPLICATION_TYPE_MOORING_SWAP,
]

# Logging: Formatter
LOGGING['formatters']['msg_only'] = {
    'format': '{message}',
    'style': '{',
}

# Logging: Handler
CRON_EMAIL_FILE_NAME = 'cron_email.log'
# logs/run_cron_tasks.log file is temporarily used in cron_tasks.py, and it's cleared whenever cron runs.
# Therefore, we need persistent log files for cron job
LOGGING['handlers']['file_cron_tasks'] = {
    'level': 'INFO',
    'class': 'logging.handlers.RotatingFileHandler',
    'filename': os.path.join(BASE_DIR, 'logs', 'cron_tasks.log'),
    'formatter': 'verbose',
    'maxBytes': 5242880
}
# Contents of this log file is emailed nightly
LOGGING['handlers']['file_cron_email'] = {
    'level': 'INFO',
    'class': 'logging.handlers.RotatingFileHandler',
    'filename': os.path.join(BASE_DIR, 'logs', CRON_EMAIL_FILE_NAME),
    'formatter': 'msg_only',
    'maxBytes': 5242880
}

# Update formatter of the existing loggers
LOGGING['formatters']['verbose2'] = {
    "format": "%(levelname)s %(asctime)s %(name)s [Line:%(lineno)s][%(funcName)s] %(message)s"
}
LOGGING['handlers']['console']['formatter'] = 'verbose2'
LOGGING['handlers']['file']['formatter'] = 'verbose2'

LOGGING['loggers']['cron_tasks'] = {
    'handlers': ['file_cron_tasks'],
    'level': 'INFO',
}
LOGGING['loggers']['cron_email'] = {
    'handlers': ['file_cron_email'],
    'level': 'INFO',
    'propagate': True,
}
LOGGING['disable_existing_loggers'] = False  # Without this line, any loggers retrieved by getLogger(__name__) are disabled.  This line should be probably placed in the settings_base.py

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

GROUP_ACCOUNT_MANAGEMENT_USER = 'Account Management'
GROUP_MOORING_LICENSING_ADMIN = 'Mooring Licensing - Admin'
GROUP_MOORING_LICENSING_PAYMENT_OFFICER = 'Mooring Licensing - Payment Officers'
GROUP_ASSESSOR_WAITING_LIST = 'Mooring Licensing - Assessors: Waiting List'
GROUP_ASSESSOR_ANNUAL_ADMISSION = 'Mooring Licensing - Assessors: Annual Admission'
GROUP_ASSESSOR_AUTHORISED_USER = 'Mooring Licensing - Assessors: Authorised User'
GROUP_ASSESSOR_MOORING_LICENCE = 'Mooring Licensing - Assessors: Mooring Site Licence'
GROUP_APPROVER_AUTHORISED_USER = 'Mooring Licensing - Approvers: Authorised User'
GROUP_APPROVER_MOORING_LICENCE = 'Mooring Licensing - Approvers: Mooring Site Licence'
GROUP_DCV_PERMIT_ADMIN = 'Mooring Licensing - DCV Permit Admin'  # DCV Permit notification is sent to the member of this group
CUSTOM_GROUPS = [
    GROUP_MOORING_LICENSING_ADMIN,
    GROUP_MOORING_LICENSING_PAYMENT_OFFICER,
    GROUP_ASSESSOR_WAITING_LIST,
    GROUP_ASSESSOR_ANNUAL_ADMISSION,
    GROUP_ASSESSOR_AUTHORISED_USER,
    GROUP_ASSESSOR_MOORING_LICENCE,
    GROUP_APPROVER_AUTHORISED_USER,
    GROUP_APPROVER_MOORING_LICENCE,
    GROUP_DCV_PERMIT_ADMIN,
]
INTERNAL_GROUPS = [
    GROUP_ACCOUNT_MANAGEMENT_USER,
    GROUP_MOORING_LICENSING_ADMIN,
    GROUP_MOORING_LICENSING_PAYMENT_OFFICER,
    GROUP_ASSESSOR_WAITING_LIST,
    GROUP_ASSESSOR_ANNUAL_ADMISSION,
    GROUP_ASSESSOR_AUTHORISED_USER,
    GROUP_ASSESSOR_MOORING_LICENCE,
    GROUP_APPROVER_AUTHORISED_USER,
    GROUP_APPROVER_MOORING_LICENCE,
    GROUP_DCV_PERMIT_ADMIN,
]

# For NumberOfDaysSettings
CODE_DAYS_BEFORE_DUE_PAYMENT = 'PaymentDueDate'
CODE_DAYS_FOR_DUE_PAYMENT_REMINDER = 'PaymentReminder'
CODE_DAYS_BEFORE_DUE_COMPLIANCE = 'ComplianceDueDate'
CODE_DAYS_BEFORE_END_OF_SIX_MONTH_PERIOD_ML = 'MLVesselNominateNotification'
CODE_DAYS_BEFORE_END_OF_SIX_MONTH_PERIOD_WLA = 'WLAVesselNominateNotification'
CODE_DAYS_BEFORE_PERIOD_MLA = 'MLApplicationSubmitNotification'
CODE_DAYS_IN_PERIOD_MLA = 'MLApplicationSubmitPeriod'
CODE_DAYS_FOR_SUBMIT_DOCUMENTS_MLA = 'MLADocumentsSubmitPeriod'
CODE_DAYS_FOR_ENDORSER_AUA = 'AUAEndorseDeclinePeriod'
CODE_DAYS_FOR_ENDORSER_AUA_REMINDER = 'AUAEndorseDeclineReminderNotification'
CODE_DAYS_FOR_RENEWAL_WLA = 'RenewalNotificationWLA'
CODE_DAYS_FOR_RENEWAL_AAP = 'RenewalNotificationAAP'
CODE_DAYS_FOR_RENEWAL_AUP = 'RenewalNotificationAUP'
CODE_DAYS_FOR_RENEWAL_ML = 'RenewalNotificationML'
CODE_DAYS_FOR_RENEWAL_DCVP = 'RenewalNotificationDCVP'
CODE_DAYS_FOR_FIRST_REMINDER = 'FirstReminderNotification'
CODE_DAYS_FOR_SECOND_REMINDER = 'SecondReminderNotification'
CODE_DAYS_FOR_FINAL_REMINDER = 'FinalReminderNotification'

TYPES_OF_CONFIGURABLE_NUMBER_OF_DAYS = [
    {
        'code': CODE_DAYS_BEFORE_DUE_PAYMENT,
        'name': 'Payment due date',
        'description': 'Number of days before due date of post-approval payments',
        'default': 14
    },
    {
        'code': CODE_DAYS_FOR_DUE_PAYMENT_REMINDER,
        'name': 'Payment due date',
        'description': 'Number of days before reminder sent for due date of post-approval payments',
        'default': 7
    },
    {
        'code': CODE_DAYS_BEFORE_DUE_COMPLIANCE,
        'name': 'Compliance due date',
        'description': 'Number of days before due date of compliance',
        'default': 28
    },
    {
        'code': CODE_DAYS_BEFORE_END_OF_SIX_MONTH_PERIOD_ML,
        'name': 'Vessel nominate notification for ML',
        'description': 'Number of days before end of six month period in which a new vessel is to be nominated for ML',
        'default': 28
    },
    {
        'code': CODE_DAYS_BEFORE_END_OF_SIX_MONTH_PERIOD_WLA,
        'name': 'Vessel nominate notification for WLA',
        'description': 'Number of days before end of six month period in which a new vessel is to be nominated for WLA',
        'default': 28
    },
    {
        'code': CODE_DAYS_BEFORE_PERIOD_MLA,
        'name': 'MLA application submit notification',
        'description': 'Number of days before end of period in which the mooring site licence application needs to be submitted',
        'default': 14
    },
    {
        'code': CODE_DAYS_IN_PERIOD_MLA,
        'name': 'MLA application submit period',
        'description': 'Number of days in which the mooring site licence application needs to be submitted.',
        'default': 28
    },  ### 1
    {
        'code': CODE_DAYS_FOR_SUBMIT_DOCUMENTS_MLA,
        'name': 'MLA documents submit period',
        'description': 'Number of days in which the additional documents for a mooring site licence application needs to be submitted.',
        'default': 28
    },  ### 2
    {
        'code': CODE_DAYS_FOR_ENDORSER_AUA,
        'name': 'AUA endorse/decline period',
        'description': 'Number of days after initial submit for the endorser to endorse/decline',
        'default': 28
    },
    {
        'code': CODE_DAYS_FOR_ENDORSER_AUA_REMINDER,
        'name': 'AUA endorse/decline period',
        'description': 'Number of days after initial submit to remind the endorser to endorse/decline',
        'default': 14
    },
    {
        'code': CODE_DAYS_FOR_RENEWAL_WLA,
        'name': 'WLA Renewal notification',
        'description': 'Number of days before expiry date of the approvals to email',
        'default': 10
    },
    {
        'code': CODE_DAYS_FOR_RENEWAL_AAP,
        'name': 'AAP Renewal notification',
        'description': 'Number of days before expiry date of the approvals to email',
        'default': 10
    },
    {
        'code': CODE_DAYS_FOR_RENEWAL_AUP,
        'name': 'AUP Renewal notification',
        'description': 'Number of days before expiry date of the approvals to email',
        'default': 10
    },
    {
        'code': CODE_DAYS_FOR_RENEWAL_ML,
        'name': 'ML Renewal notification',
        'description': 'Number of days before expiry date of the approvals to email',
        'default': 10
    },
    {
        'code': CODE_DAYS_FOR_RENEWAL_DCVP,
        'name': 'DCVP Renewal notification',
        'description': 'Number of days before expiry date of the approvals to email',
        'default': 14
    },
    {
        'code': CODE_DAYS_FOR_FIRST_REMINDER,
        'name': 'First Reminder notification period',
        'description': 'Number of days before the end date to send the first reminder',
        'default': 14
    },
    {
        'code': CODE_DAYS_FOR_SECOND_REMINDER,
        'name': 'Second Reminder notification period',
        'description': 'Number of days before the end date to send the second reminder',
        'default': 7
    },
    {
        'code': CODE_DAYS_FOR_FINAL_REMINDER,
        'name': 'Final Reminder notification period',
        'description': 'Number of days before the end date to send the final reminder',
        'default': 1
    },
]

# Oracle codes
ORACLE_CODE_ID_WL = 'oracle_code_wl'
ORACLE_CODE_ID_AA = 'oracle_code_aa'
ORACLE_CODE_ID_AU = 'oracle_code_au'
ORACLE_CODE_ID_ML = 'oracle_code_ml'
ORACLE_CODE_ID_DCV_PERMIT = 'oracle_code_dcv_permit'
ORACLE_CODE_ID_DCV_ADMISSION = 'oracle_code_dcv_admission'
ORACLE_CODE_ID_REPLACEMENT_STICKER = 'oracle_code_replacement_sticker'
ORACLE_CODE_ID_MOORING_SWAP = 'oracle_code_mooring_swap'
ORACLE_CODES = [
    {
        'identifier': ORACLE_CODE_ID_WL,
        'name': 'Waiting list allocation fees',
    },
    {
        'identifier': ORACLE_CODE_ID_AA,
        'name': 'Annual admission fees',
    },
    {
        'identifier': ORACLE_CODE_ID_AU,
        'name': 'Authorised user fees',
    },
    {
        'identifier': ORACLE_CODE_ID_ML,
        'name': 'Mooring site licence fees',
    },
    {
        'identifier': ORACLE_CODE_ID_DCV_PERMIT,
        'name': 'DCV permit fees',
    },
    {
        'identifier': ORACLE_CODE_ID_DCV_ADMISSION,
        'name': 'DCV admission fees',
    },
    {
        'identifier': ORACLE_CODE_ID_REPLACEMENT_STICKER,
        'name': 'Replacement sticker fees',
    },
    {
        'identifier': ORACLE_CODE_ID_MOORING_SWAP,
        'name': 'Mooring swap fees',
    },
]
# For django-smart-select
USE_DJANGO_JQUERY = True
## DoT vessel rego lookup
DOT_URL=env('DOT_URL',None)
DOT_USERNAME=env('DOT_USERNAME',None)
DOT_PASSWORD=env('DOT_PASSWORD',None)
DO_DOT_CHECK=env('DO_DOT_CHECK', False)
LOV_CACHE_TIMEOUT=10800
CSRF_MIDDLEWARE_TOKEN=env('CSRF_MIDDLEWARE_TOKEN', '')
EMAIL_INSTANCE = env('EMAIL_INSTANCE','DEV')
os.environ['UPDATE_PAYMENT_ALLOCATION'] = 'True'
UNALLOCATED_ORACLE_CODE = 'NNP449 GST'

CRON_CLASSES = [
    'appmonitor_client.cron.CronJobAppMonitorClient',
    'ledger_api_client.cron.CronJobLedgerTotals',
]

# Is licence holder allowed to operate
APPROVED_OPERATIONAL_STATUS = ['current', ]

# Use git commit hash for purging cache in browser for deployment changes
GIT_COMMIT_HASH = ''
GIT_COMMIT_DATE = ''
LEDGER_TEMPLATE = 'bootstrap5'

# Change to file session backend to improve web application speed
SESSION_ENGINE = 'django.contrib.sessions.backends.file'
if EMAIL_INSTANCE == 'DEV' or EMAIL_INSTANCE == 'UAT' or EMAIL_INSTANCE == 'TEST':
    SESSION_FILE_PATH = env('SESSION_FILE_PATH', BASE_DIR+'/session_store/')
    if not os.path.isdir(SESSION_FILE_PATH):
        os.mkdir(SESSION_FILE_PATH)       
else:
    SESSION_FILE_PATH = env('SESSION_FILE_PATH', '/app/session_store/')

LEDGER_UI_ACCOUNTS_MANAGEMENT = [
    {'first_name': {'options' : {'view': True, 'edit': True}}},
    {'last_name': {'options' : {'view': True, 'edit': True}}},
    {'residential_address': {'options' : {'view': True, 'edit': True}}},
    {'postal_address': {'options' : {'view': True, 'edit': True}}},
    {'phone_number' : {'options' : {'view': True, 'edit': True}}},
    {'mobile_number' : {'options' : {'view': True, 'edit': True}}},
    {'dob' : {'options' : {'view': True, 'edit': True}}},
    {'postal_same_as_residential' : {'options' : {'view': True, 'edit': True}}},
    {'address_details' : {'options' : {'billing_address': {'show': False}}}},
]
LEDGER_UI_SYSTEM_ACCOUNTS_MANAGEMENT['address_details']['options']['billing_address']['show'] = False
FILE_UPLOAD_PERMISSIONS = None
MOORING_LICENSING_EXTERNAL_URL = env('MOORING_LICENSING_EXTERNAL_URL', 'External url not configured')
PRIVATE_MEDIA_DIR_NAME = env('PRIVATE_MEDIA_DIR_NAME', 'private-media')
PRIVATE_MEDIA_STORAGE_LOCATION = os.path.join(BASE_DIR, PRIVATE_MEDIA_DIR_NAME)
PRIVATE_MEDIA_BASE_URL = f'/{PRIVATE_MEDIA_DIR_NAME}/'
MAKE_PRIVATE_MEDIA_FILENAME_NON_GUESSABLE = env('MAKE_PRIVATE_MEDIA_FILENAME_NON_GUESSABLE', False)
LEDGER_UI_CARDS_MANAGEMENT = env('LEDGER_UI_CARDS_MANAGEMENT', True)
SESSION_COOKIE_AGE = env('SESSION_COOKIE_AGE', 3600)
CANCELATION_POLICY_URL = env('CANCELATION_POLICY_URL', 'https://ria.wa.gov.au/boating')
AUTO_CANCEL_APPROVAL_WHEN_GRACE_PERIOD_EXPIRED = env('AUTO_CANCEL_APPROVAL_WHEN_GRACE_PERIOD_EXPIRED', False)  # RIA doesn't want any auto process triggered when the grace period expired.
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"
PREVIOUS_PAYMENT_REASON = env('PREVIOUS_PAYMENT_REASON', "Previous payment made")

CSRF_TRUSTED_ORIGINS_STRING = decouple.config("CSRF_TRUSTED_ORIGINS", default='[]')
CSRF_TRUSTED_ORIGINS = json.loads(str(CSRF_TRUSTED_ORIGINS_STRING))