# Prepare the base environment.
FROM ubuntu:24.10 as builder_base_mooringlicensing
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
ENV NODE_MAJOR=20

#ARG BRANCH_ARG
#ARG REPO_ARG
#ARG REPO_NO_DASH_ARG
#ENV BRANCH=$BRANCH_ARG
#ENV REPO=$REPO_ARG
#ENV REPO_NO_DASH=$REPO_NO_DASH_ARG
#RUN sed 's/archive.ubuntu.com/mirror.enzu.com/g' /etc/apt/sources.list.d/ubuntu.sources > /etc/apt/sources.list.d/ubuntu.sources
#RUN sed 's/secuirty.ubuntu.com/mirror.enzu.com/g' /etc/apt/sources.list.d/ubuntu.sources > /etc/apt/sources.list.d/ubuntu.sources
# RUN mv /etc/apt/sources.list.d/ubuntu-new.sources /etc/apt/sources.list.d/ubuntu.sources


RUN apt-get clean
RUN apt-get update
RUN apt-get upgrade -y
RUN apt-get install --no-install-recommends -y curl wget git libmagic-dev gcc binutils libproj-dev gdal-bin python3 python3-setuptools python3-dev python3-pip tzdata rsyslog gunicorn virtualenv
RUN apt-get install --no-install-recommends -y libpq-dev patch libreoffice
RUN apt-get install --no-install-recommends -y postgresql-client mtr htop vim nano npm sudo
RUN apt-get install --no-install-recommends -y bzip2 unzip
RUN apt-get install --no-install-recommends -y graphviz libgraphviz-dev pkg-config
RUN ln -s /usr/bin/python3 /usr/bin/python 
RUN apt remove -y libnode-dev
RUN apt remove -y libnode72

# Install nodejs
RUN update-ca-certificates
# install node 16
#RUN touch install_node.sh
#RUN curl -fsSL https://deb.nodesource.com/setup_20.x -o install_node.sh
#RUN chmod +x install_node.sh && ./install_node.sh
#RUN apt-get install -y nodejs

RUN mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_$NODE_MAJOR.x nodistro main" \
    | tee /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y nodejs

# Install nodejs
COPY startup.sh pre_startup.sh /
COPY ./timezone /etc/timezone
RUN chmod 755 /startup.sh && \
    chmod +s /startup.sh && \
    chmod 755 /pre_startup.sh && \
    chmod +s /pre_startup.sh && \
    groupadd -g 5000 oim && \
    useradd -g 5000 -u 5000 oim -s /bin/bash -d /app && \
    usermod -a -G sudo oim && \
    echo "oim  ALL=(ALL)  NOPASSWD: /startup.sh" > /etc/sudoers.d/oim && \
    mkdir /app && \
    chown -R oim.oim /app && \
    mkdir /container-config/ && \
    chown -R oim.oim /container-config/ && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    touch /app/rand_hash
    
RUN chmod 755 /pre_startup.sh 

# Default Scripts
RUN wget https://raw.githubusercontent.com/dbca-wa/wagov_utils/main/wagov_utils/bin/default_script_installer.sh -O /tmp/default_script_installer.sh
RUN chmod 755 /tmp/default_script_installer.sh
RUN /tmp/default_script_installer.sh

# Install Python libs from requirements.txt.
FROM builder_base_mooringlicensing as python_libs_ml
WORKDIR /app
USER oim
RUN virtualenv /app/venv
ENV PATH=/app/venv/bin:$PATH
RUN git config --global --add safe.directory /app
COPY python-cron ./
#RUN PATH=/app/.local/bin:$PATH
COPY --chown=oim:oim requirements.txt ./

RUN pip install -r requirements.txt 
#  && rm -rf /var/lib/{apt,dpkg,cache,log}/ /tmp/* /var/tmp/*
RUN pip install --upgrade pip
#RUN wget -O /tmp/GDAL-3.8.3-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl https://github.com/girder/large_image_wheels/raw/wheelhouse/GDAL-3.8.3-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl#sha256=e2fe6cfbab02d535bc52c77cdbe1e860304347f16d30a4708dc342a231412c57
#RUN pip install /tmp/GDAL-3.8.3-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl
# Install the project (ensure that frontend projects have been built prior to this step).
FROM python_libs_ml
COPY  --chown=oim:oim gunicorn.ini manage_ml.py ./
#COPY timezone /etc/timezone
#RUN echo "Australia/Perth" > /etc/timezone
#ENV TZ=Australia/Perth
#RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
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

RUN mkdir /app/tmp/
RUN chmod 777 /app/tmp/


# IPYTHONDIR - Will allow shell_plus (in Docker) to remember history between sessions
# 1. will create dir, if it does not already exist
# 2. will create profile, if it does not already exist
RUN mkdir /app/logs/.ipython
RUN export IPYTHONDIR=/app/logs/.ipython/
#RUN python profile create 

EXPOSE 8080
HEALTHCHECK --interval=1m --timeout=5s --start-period=10s --retries=3 CMD ["wget", "-q", "-O", "-", "http://localhost:8080/"]
CMD ["/startup.sh"]

