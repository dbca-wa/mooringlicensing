import datetime
import logging
import pytz
import os
from django.apps import apps
import json

logger = logging.getLogger(__name__)

app_label = "mooringlicensing"
# add through models here to produce a different set of follow relationships
through_model_keys = [
        'userdelegation',
        #'feeitemapplicationfee',
        'vesselownership',
        'companyownership',
        'mooringonapproval',
        'vesselownershiponapproval'
        ]

# do not list reversions for these models
ignore_keys = []

## call this utility function in shell_plus to write the file reversion_utility_output.txt into the root folder of this app
def print_reversion_registrations():
    registration_dict = {}
    for key in apps.all_models.get(app_label).keys():
        model = apps.all_models.get(app_label).get(key)
        model_name = model._meta.label.split('.')[1]
        follow = []
        #import ipdb; ipdb.set_trace()
        if key in ignore_keys:
            continue
        elif key in through_model_keys:
            for field in apps.all_models.get(app_label).get(key)._meta.fields:
                if field.related_model:
                    follow.append(field.name)
        else:
            for field in apps.all_models.get(app_label).get(key)._meta.related_objects:
                if not field.parent_link and field.name not in ignore_keys:
                    follow.append(field.related_name if field.related_name else field.name + "_set")
        if key not in registration_dict.keys():
            registration_dict[key] = {
                    "registration_str": "reversion.register({}, follow={})".format(model_name, follow),
                    "module": model.__module__.split('.')[2],
                    "name": model._meta.label.split('.')[1],
                    }

    registration_ord_dict = {}
    ## add modules to registration_ord_dict
    for entry in registration_dict.keys():
        module = registration_dict[entry].get("module")
        if module not in registration_ord_dict.keys():
            registration_ord_dict[module] = {}
    ## now add model entries to modules
    for model in registration_dict.keys():
        module = registration_dict[model].get("module")
        model_name = registration_dict[model].get("name")
        for ord_module in registration_ord_dict.keys():
            if (
                    ord_module == module and 
                    model not in registration_ord_dict[ord_module].keys() and 
                    '_' not in model_name # not a real model
                    ):
                registration_ord_dict[ord_module][model_name] = registration_dict[model].get("registration_str")
    ## print to file
    with open('reversion_utility_output.txt', 'w') as f:
        for key, value in registration_ord_dict.items():
            f.write("\n{}\n".format(key))
            for model, registration in registration_ord_dict[key].items():
                f.write("{}\n".format(registration))

