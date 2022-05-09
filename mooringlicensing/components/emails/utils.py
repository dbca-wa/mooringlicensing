from django.conf import settings
from ledger.accounts.models import EmailUser


def get_user_as_email_user(sender):
    try:
        sender_user = EmailUser.objects.get(email__icontains=sender)
    except:
        EmailUser.objects.create(email=sender, password='')
        sender_user = EmailUser.objects.get(email__icontains=sender)
    return sender_user


def make_url_for_internal(url):
    if '-internal' not in url:
        if '-dev' in url:
            url = url.replace('-dev', '-dev-internal')
        elif '-uat' in url:
            url = url.replace('-uat', '-uat-internal')
        else:
            url = url.replace('.dbca.wa.gov.au', '-internal.dbca.wa.gov.au')
    return url


def make_url_for_external(url):
    # Public URL should not have 'internal' substring
    if '-dev-internal' in url:
        web_url = url.replace('-dev-internal', '-dev')
    elif '-uat-internal' in url:
        web_url = url.replace('-uat-internal', '-uat')
    else:
        web_url = url.replace('-internal', '')

    return web_url


def get_public_url(request=None):
    if request:
        web_url = '{}://{}'.format(request.scheme, request.get_host())
    else:
        web_url = settings.SITE_URL if settings.SITE_URL else ''

    # Make http https
    if web_url.startswith('http') and not web_url.startswith('https'):
        web_url = web_url.replace('http', 'https', 1)

    # Public URL should not have 'internal' substring
    web_url = make_url_for_external(web_url)

    return web_url
