import sys

from django.core.exceptions import ImproperlyConfigured

import os
from confy import env
import confy
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
confy.read_environment_file(BASE_DIR+"/.env")
os.environ.setdefault("BASE_DIR", BASE_DIR)

from ledger.settings_base import *

ROOT_URLCONF = 'mooringlicensing.urls'
SITE_ID = 1
DEPT_DOMAINS = env('DEPT_DOMAINS', ['dpaw.wa.gov.au', 'dbca.wa.gov.au'])
SYSTEM_MAINTENANCE_WARNING = env('SYSTEM_MAINTENANCE_WARNING', 24) # hours
DISABLE_EMAIL = env('DISABLE_EMAIL', False)
SHOW_TESTS_URL = env('SHOW_TESTS_URL', False)
SHOW_DEBUG_TOOLBAR = env('SHOW_DEBUG_TOOLBAR', False)

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
    'smart_selects',
    'reversion_compare',
    'bootstrap3',
    'mooringlicensing',
    'mooringlicensing.components.main',
    'mooringlicensing.components.emails',
    'mooringlicensing.components.organisations',
    'mooringlicensing.components.users',
    'mooringlicensing.components.proposals',
    'mooringlicensing.components.approvals',
    'mooringlicensing.components.compliances',
    'mooringlicensing.components.payments_ml',
    'taggit',
    'rest_framework',
    'rest_framework_datatables',
    'rest_framework_gis',
    'reset_migrations',
    'ckeditor',
]

ADD_REVERSION_ADMIN=True

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
        'rest_framework_datatables.renderers.DatatablesRenderer',
    ),
}

MIDDLEWARE_CLASSES += [
    'mooringlicensing.middleware.FirstTimeNagScreenMiddleware',
    'mooringlicensing.middleware.RevisionOverrideMiddleware',
    'mooringlicensing.middleware.CacheControlMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
]

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
ADMIN_GROUP = env('ADMIN_GROUP', 'Mooring Licensing - Admin')
CRON_RUN_AT_TIMES = env('CRON_RUN_AT_TIMES', '04:05')
CRON_EMAIL = env('CRON_EMAIL', 'cron@' + SITE_DOMAIN).lower()
CRON_NOTIFICATION_EMAIL = env('CRON_NOTIFICATION_EMAIL', NOTIFICATION_EMAIL).lower()
EMAIL_FROM = DEFAULT_FROM_EMAIL
os.environ['LEDGER_PRODUCT_CUSTOM_FIELDS'] = "('ledger_description','quantity','price_incl_tax','price_excl_tax','oracle_code')"

BASE_URL=env('BASE_URL')

CKEDITOR_CONFIGS = {
    'default': {
        'toolbar': 'full',
        'height': 300,
        'width': '100%',
    },
    'awesome_ckeditor': {
        'toolbar': 'Basic',
    },
}

CONSOLE_EMAIL_BACKEND = env('CONSOLE_EMAIL_BACKEND', False)
if CONSOLE_EMAIL_BACKEND:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

#PAYMENT_SYSTEM_ID = env('PAYMENT_SYSTEM_ID', 'S651')
## do not read from env
PAYMENT_SYSTEM_ID = 'S651'
OSCAR_BASKET_COOKIE_OPEN = 'mooringlicensing_basket'
PS_PAYMENT_SYSTEM_ID = PAYMENT_SYSTEM_ID
PAYMENT_SYSTEM_PREFIX = env('PAYMENT_SYSTEM_PREFIX', PAYMENT_SYSTEM_ID.replace('S', '0'))

MOORING_BOOKINGS_API_KEY=env('MOORING_BOOKINGS_API_KEY')
MOORING_BOOKINGS_API_URL=env('MOORING_BOOKINGS_API_URL')

PROPOSAL_TYPE_NEW = 'new'
PROPOSAL_TYPE_RENEWAL = 'renewal'
PROPOSAL_TYPE_AMENDMENT = 'amendment'
PROPOSAL_TYPES_FOR_FEE_ITEM = [
    (PROPOSAL_TYPE_NEW, 'New Application'),
    (PROPOSAL_TYPE_AMENDMENT, 'Amendment'),
    (PROPOSAL_TYPE_RENEWAL, 'Renewal'),
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

# Add a formatter for the contents of the cron email
LOGGING['formatters']['msg_only'] = {
    'format': '{message}',
    'style': '{',
}

# Add a handler
CRON_EMAIL_FILE_NAME = 'cron_email.log'
LOGGING['handlers']['file_mooringlicensing'] = {
    'level': 'INFO',
    'class': 'logging.handlers.RotatingFileHandler',
    'filename': os.path.join(BASE_DIR, 'logs', 'mooringlicensing.log'),
    'formatter': 'verbose',
    'maxBytes': 5242880
}
# logs/run_cron_tasks.log file is temporarily used in cron_tasks.py, and it's cleared whenever cron runs.
# Therefore we need persistent log files for cron job
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
LOGGING['handlers']['console'] = {
    'level': 'DEBUG',
    'class': 'logging.StreamHandler',
    'stream': sys.stdout,
    'formatter': 'verbose',
}

# Define loggers
LOGGING['loggers']['mooringlicensing'] = {
    'handlers': ['file_mooringlicensing', 'console'],
    'level': 'DEBUG',
}
LOGGING['loggers']['cron_tasks'] = {
    'handlers': ['file_cron_tasks'],
    'level': 'INFO',
}
LOGGING['loggers']['cron_email'] = {
    'handlers': ['file_cron_email'],
    'level': 'INFO',
    'propagate': True,
}

# Logging all to mooringlicensing.log file
LOGGING['loggers']['']['handlers'].append('file_mooringlicensing')

GROUP_MOORING_LICENSING_ADMIN = 'Mooring Licensing - Admin'
GROUP_MOORING_LICENSING_PAYMENT_OFFICER = 'Mooring Licensing - Payment Officers'
GROUP_ASSESSOR_WAITING_LIST = 'Mooring Licensing - Assessors: Waiting List'
GROUP_ASSESSOR_ANNUAL_ADMISSION = 'Mooring Licensing - Assessors: Annual Admission'
GROUP_ASSESSOR_AUTHORISED_USER = 'Mooring Licensing - Assessors: Authorised User'
GROUP_ASSESSOR_MOORING_LICENCE = 'Mooring Licensing - Assessors: Mooring Licence'
GROUP_APPROVER_AUTHORISED_USER = 'Mooring Licensing - Approvers: Authorised User'
GROUP_APPROVER_MOORING_LICENCE = 'Mooring Licensing - Approvers: Mooring Licence'
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

# For NumberOfDaysSettings
CODE_DAYS_BEFORE_DUE_COMPLIANCE = 'ComplianceDueDate'
CODE_DAYS_BEFORE_END_OF_SIX_MONTH_PERIOD_ML = 'MLVesselNominateNotification'
CODE_DAYS_BEFORE_END_OF_SIX_MONTH_PERIOD_WLA = 'WLAVesselNominateNotification'
CODE_DAYS_BEFORE_PERIOD_MLA = 'MLApplicationSubmitNotification'
CODE_DAYS_IN_PERIOD_MLA = 'MLApplicationSubmitPeriod'
CODE_DAYS_FOR_SUBMIT_DOCUMENTS_MLA = 'MLADocumentsSubmitPeriod'
CODE_DAYS_FOR_ENDORSER_AUA = 'AUAEndorseDeclinePeriod'
CODE_DAYS_FOR_RENEWAL_WLA = 'RenewalNotificationWLA'
CODE_DAYS_FOR_RENEWAL_AAP = 'RenewalNotificationAAP'
CODE_DAYS_FOR_RENEWAL_AUP = 'RenewalNotificationAUP'
CODE_DAYS_FOR_RENEWAL_ML = 'RenewalNotificationML'
CODE_DAYS_FOR_RENEWAL_DCVP = 'RenewalNotificationDCVP'

TYPES_OF_CONFIGURABLE_NUMBER_OF_DAYS = [
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
        'description': 'Number of days before end of period in which the mooring licence application needs to be submitted',
        'default': 14
    },
    {
        'code': CODE_DAYS_IN_PERIOD_MLA,
        'name': 'MLA application submit period',
        'description': 'Number of days in which the mooring licence application needs to be submitted.',
        'default': 28
    },  ### 1
    {
        'code': CODE_DAYS_FOR_SUBMIT_DOCUMENTS_MLA,
        'name': 'MLA documents submit period',
        'description': 'Number of days in which the additional documents for a mooring licence application needs to be submitted.',
        'default': 28
    },  ### 2
    {
        'code': CODE_DAYS_FOR_ENDORSER_AUA,
        'name': 'AUA endorse/decline period',
        'description': 'Number of days after initial submit for the endorser to endorse/decline',
        'default': 28
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
        'default': 10
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
        'name': 'Mooring licence fees',
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
    'mooringlicensing.cron.OracleIntegrationCronJob',
]

# Is licence holder allowed to operate
APPROVED_OPERATIONAL_STATUS = ['current', ]
# Is licence/permit still approved?  Other than cancelled, expired or surrendered
APPROVED_APPROVAL_STATUS = ['current', 'suspended', ]

# Use git commit hash for purging cache in browser for deployment changes
GIT_COMMIT_HASH = ''
GIT_COMMIT_DATE = ''
# not required
#if  os.path.isdir(BASE_DIR+'/.git/') is True:
#    GIT_COMMIT_DATE = os.popen('cd '+BASE_DIR+' ; git log -1 --format=%cd').read()
#    GIT_COMMIT_HASH = os.popen('cd  '+BASE_DIR+' ; git log -1 --format=%H').read()
#if len(GIT_COMMIT_HASH) == 0: 
#    GIT_COMMIT_HASH = os.popen('cat /app/git_hash').read()
#    if len(GIT_COMMIT_HASH) == 0:
#       print ("ERROR: No git hash provided")

