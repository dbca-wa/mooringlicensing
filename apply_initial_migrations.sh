#!/bin/bash

# This file is supposed to be run on the empty database for the application (segregated)

MANAGE_PY_FILE_NAME="manage_ml.py"
FILE="pyproject.toml"


# Determine if the 'poetry' is used for virtual environment
if [[ -f "$FILE" ]]; then
    # pyproject.toml file exists.
    echo "poetry env"
    RUN_PYTHON="poetry run python"
    DJANGO_FOLDER="venv/lib/python3.8/site-packages/django/"  # TODO: correct the folder path
else
    echo "no env"
    # pyproject.toml file doesn't exist.
    RUN_PYTHON="python"
    DJANGO_FOLDER="venv/lib/python3.8/site-packages/django/"
fi


# Apply patches
patch ./mooringlicensing/migrations/0001_initial.py < patch.mooringlicensing.0001_initial.py.patch &&
patch ${DJANGO_FOLDER}contrib/admin/migrations/0001_initial.py < patch.admin.0001_initial.py.patch &&
status=$?
if [ $status -ne 0  ]; then
    echo "Migration patch filed: $status"
    exit $status
fi


# Migrations
$RUN_PYTHON $MANAGE_PY_FILE_NAME migrate auth
$RUN_PYTHON $MANAGE_PY_FILE_NAME migrate ledger_api_client &&
$RUN_PYTHON $MANAGE_PY_FILE_NAME migrate admin


# Revert patches
patch ${DJANGO_FOLDER}contrib/admin/migrations/0001_initial.py < patch.admin.0001_initial.py.patch_revert &&
#patch ./mooringlicensing/migrations/0001_initial.py < patch.mooringlicensing.0001_initial.py.patch_revert &&
status=$?
if [ $status -ne 0  ]; then
    echo "Migration patch filed: $status"
    exit $status
fi


$RUN_PYTHON $MANAGE_PY_FILE_NAME migrate django_cron &&
$RUN_PYTHON $MANAGE_PY_FILE_NAME migrate sites 0001_initial &&
$RUN_PYTHON $MANAGE_PY_FILE_NAME migrate sites 0002_alter_domain_unique &&
$RUN_PYTHON $MANAGE_PY_FILE_NAME migrate sessions #&&
#$RUN_PYTHON $MANAGE_PY_FILE_NAME migrate
#$RUN_PYTHON $MANAGE_PY_FILE_NAME dbshell -- -c 'ALTER TABLE django_admin_log RENAME COLUMN "user" TO "user_id";'


# Revert patches
#patch ${DJANGO_FOLDER}contrib/admin/migrations/0001_initial.py < patch.admin.0001_initial.py.patch_revert &&
#patch ./mooringlicensing/migrations/0001_initial.py < patch.mooringlicensing.0001_initial.py.patch_revert &&
#status=$?
#if [ $status -ne 0  ]; then
#    echo "Migration patch filed: $status"
#    exit $status
#fi