from django.conf import settings
from ledger_api_client.ledger_models import EmailUserRO as EmailUser
import logging

logger = logging.getLogger(__name__)

def get_user_as_email_user(sender):
    try:
        sender_user = EmailUser.objects.filter(email__iexact=sender, is_active=True).order_by('-id').first()
    except:
        sender_user = None
    return sender_user


def make_url_for_internal(url):
    if '-internal' not in url:
        if '-dev' in url:
            url = url.replace('-dev', '-dev-internal')
        elif '-uat' in url:
            url = url.replace('-uat', '-uat-internal')
        else:
            url = url.replace('.dbca.wa.gov.au', '-internal.dbca.wa.gov.au')

    url = make_http_https(url)
    return url


def make_url_for_external(url):
    # Public URL should not have 'internal' substring
    if '-dev-internal' in url:
        url = url.replace('-dev-internal', '-dev')
    elif '-uat-internal' in url:
        url = url.replace('-uat-internal', '-uat')
    else:
        url = url.replace('-internal', '')

    # For seg-dev environment
    if '-ria-seg-dev' in url:
        url = url.replace('-ria-seg-dev', '-seg-dev')

    web_url = make_http_https(url)

    return web_url


def get_public_url():
    if not settings.SITE_URL:
        logger.error("Site URL not set, link cannot be provided")

    web_url = settings.SITE_URL if settings.SITE_URL else ''
    return web_url


def make_http_https(web_url):
    if web_url.startswith('http') and not web_url.startswith('https'):
        web_url = web_url.replace('http', 'https', 1)
    return web_url
