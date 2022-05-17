# Mooring Licensing System
The Marine Administration System is used by customers applying for an Annual Admission Permit, Authorised User Permit or Mooring Licence from the Rottnest Island Authority, The system can also be used to apply for a position on the waiting list for a Mooring Licence. The system is used by RIA staff to process the applications and to manage issued approvals.

It is a database-backed Django application, using REST API with Vue.js as the client side app and integrates into the ledger system.

# Requirements and installation

- Python (3.8.x)
- PostgreSQL (>=11)

Python library requirements should be installed using `pip`:

`pip install -r requirements.txt`

## Vue JS
Root of the Vue Js folder has package.json, which has the list of packages to be installed plus commands on to build the software and start the dev server.

In the root folder, install packages with `npm install`.

Then, run `npm run build` to build the software and move the output files to `mooringlicensing/static/mooringlicensing_vue`.

The build files are made available to the Django app by running `python manage.py collectstatic --no-input`.

If the `DEV_APP_BUILD_URL` is not set, the Django app will serve static Javascript from `staticfiles_ml/mooringlicensing_vue/js.app.js`, 
else the Vue app will be served from the url provided.  Start the dev server with `npm start`.

# Environment variables

A `.env` file should be created in the project root and used to set
required environment variables at run time. Example content:

    DEBUG=True
    SECRET_KEY='thisismysecret'
    DATABASE_URL='postgis://user:pw@localhost:port/db_name'
    EMAIL_HOST='SMTP_HOST'
    BPOINT_USERNAME='BPOINT_USER'
    BPOINT_PASSWORD='BPOINT_PW
    BPOINT_BILLER_CODE='1234567'
    BPOINT_MERCHANT_NUM='BPOINT_MERCHANT_NUM'
    BPAY_BILLER_CODE='987654'
    PAYMENT_OFFICERS_GROUP='PAYMENT_GROUP'
    DEFAULT_FROM_EMAIL='FROM_EMAIL_ADDRESS'
    NOTIFICATION_EMAIL='NOTIF_RECIPIENT_1, NOTIF_RECIPIENT_2'
    NON_PROD_EMAIL='NON_PROD_RECIPIENT_1, NON_PROD_RECIPIENT_2'
    EMAIL_INSTANCE='DEV'
    PRODUCTION_EMAIL=False
    BPAY_ALLOWED=False
    SITE_PREFIX='prefix'
    SITE_DOMAIN='SITE_DOMAIN'
    LEDGER_GST=10
    DISABLE_EMAIL=True
    DJANGO_HTTPS=True
    CRON_NOTIFICATION_EMAIL='email'
    ENABLE_DJANGO_LOGIN=True
    OSCAR_SHOP_NAME='shop_name'
    # Below is required to run Vue Js front end with hot reload
    DEV_APP_BUILD_URL="http://localhost:8080/app.js"
    # Below prints emails to screen instead of sending via mail server
    CONSOLE_EMAIL_BACKEND=True
