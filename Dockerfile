# Prepare the base environment.
FROM ghcr.io/dbca-wa/docker-apps-dev:ubuntu_2604_base_python_node as builder_base_mooringlicensing
MAINTAINER asi@dbca.wa.gov.au

ENV DEBIAN_FRONTEND=noninteractive
#ENV DEBUG=True
ENV TZ=Australia/Perth
ENV DEFAULT_FROM_EMAIL='no-reply@dbca.wa.gov.au'
ENV NOTIFICATION_EMAIL='no-reply@dbca.wa.gov.au'
ENV NON_PROD_EMAIL='none@none.com'
ENV PRODUCTION_EMAIL=False
ENV EMAIL_INSTANCE='DEV'
ENV SECRET_KEY="ThisisNotRealKey"
ENV SITE_PREFIX='mls-dev'
ENV SITE_DOMAIN='dbca.wa.gov.au'
ENV OSCAR_SHOP_NAME='No Name'
ENV BPAY_ALLOWED=False
ENV NODE_MAJOR=24

RUN apt-get clean
RUN apt-get update
RUN apt-get upgrade -y

COPY startup.sh pre_startup.sh /
COPY ./timezone /etc/timezone
RUN chmod 755 /startup.sh && \
    chmod +s /startup.sh && \
    chmod 755 /pre_startup.sh && \
    chmod +s /pre_startup.sh && \
    groupadd -g 5000 oim && \
    useradd -g 5000 -u 5000 oim -s /bin/bash -d /app && \
    mkdir /app && \
    chown -R oim.oim /app && \
    mkdir /container-config/ && \
    chown -R oim.oim /container-config/ && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    touch /app/rand_hash
    
RUN chmod 755 /pre_startup.sh 

# Install Python libs from requirements.txt.
FROM builder_base_mooringlicensing as python_libs_ml
WORKDIR /app
USER oim

ENV VIRTUAL_ENV=/app/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH=$VIRTUAL_ENV/bin:$PATH

RUN git config --global --add safe.directory /app
COPY python-cron ./
#RUN PATH=/app/.local/bin:$PATH
COPY --chown=oim:oim requirements.txt ./

RUN pip install -r requirements.txt 
#  && rm -rf /var/lib/{apt,dpkg,cache,log}/ /tmp/* /var/tmp/*
RUN pip install --upgrade pip

FROM python_libs_ml
COPY  --chown=oim:oim gunicorn.ini manage_ml.py ./

RUN touch /app/.env
COPY  --chown=oim:oim .git ./.git
COPY  --chown=oim:oim mooringlicensing ./mooringlicensing
COPY  --chown=oim:oim patch_for_admin_0001_initial.patch ./patch_for_admin_0001_initial.patch
COPY  --chown=oim:oim patch_for_admin_0001_initial.patch_revert ./patch_for_admin_0001_initial.patch_revert
COPY  --chown=oim:oim patch_for_reversion_0001.patch ./patch_for_reversion_0001.patch
COPY  --chown=oim:oim patch_for_reversion_0001.patch_revert ./patch_for_reversion_0001.patch_revert

RUN cd /app/mooringlicensing/frontend/mooringlicensing/; npm install
RUN cd /app/mooringlicensing/frontend/mooringlicensing/; npm run build

RUN python manage_ml.py collectstatic --noinput
RUN python manage_ml.py script_hash_indexes --skip-checks

RUN mkdir /app/tmp/
RUN chmod 777 /app/tmp/


# IPYTHONDIR - Will allow shell_plus (in Docker) to remember history between sessions
# 1. will create dir, if it does not already exist
# 2. will create profile, if it does not already exist
RUN mkdir /app/logs/.ipython
RUN export IPYTHONDIR=/app/logs/.ipython/
#RUN python profile create 

# Cleanup
USER root
RUN wget https://raw.githubusercontent.com/dbca-wa/wagov_utils/refs/heads/main/wagov_utils/bin/package_cleanup_2604.sh -O /tmp/package_cleanup_2604.sh
RUN chmod 755 /tmp/package_cleanup_2604.sh
RUN /tmp/package_cleanup_2604.sh
USER oim

EXPOSE 8080
HEALTHCHECK --interval=1m --timeout=5s --start-period=10s --retries=3 CMD ["wget", "-q", "-O", "-", "http://localhost:8080/"]
CMD ["/startup.sh"]

