
module.exports = {
    application_types:"/api/application_types",
    application_types_dict:"/api/application_types_dict",
    application_statuses_dict:"/api/application_statuses_dict",
    applicants_dict: "/api/applicants_dict",
    vessel_types_dict:"/api/vessel_types_dict",
    insurance_choices_dict:"/api/insurance_choices_dict",
    vessel_rego_nos:"/api/vessel_rego_nos",
    mooring_lookup:"/api/mooring_lookup",
    mooring_lookup_per_bay:"/api/mooring_lookup_per_bay",
    vessel_lookup:"/api/vessel_lookup",
    company_names:"/api/company_names",
    dcv_vessel_rego_nos:"/api/dcv_vessel_rego_nos",
    fee_configurations: "/api/fee_configurations",
    approval_types_dict:"/api/approval_types_dict",
    approval_statuses_dict:"/api/approval_statuses_dict",
    fee_seasons_dict:"/api/fee_seasons_dict",
    compliance_statuses_dict:"/api/compliance_statuses_dict",
    mooring_statuses_dict:"/api/mooring_statuses_dict",
    mooring_bays:"/api/mooringbays.json",
    seasons_for_dcv_dict: "/api/seasons_for_dcv_dict",

    profile: '/api/profile',
    submitter_profile: '/api/submitter_profile',
    organisations: '/api/organisations.json',
    filtered_organisations: '/api/filtered_organisations',
    organisation_requests: '/api/organisation_requests.json',
    organisation_contacts: '/api/organisation_contacts.json',
    organisation_access_group_members: '/api/organisation_access_group_members',
    users: '/api/users.json',
    department_users: '/api/department_users',
    filtered_users: '/api/filtered_users',
    countries: "https://restcountries.eu/rest/v1/?fullText=true",

    proposals_paginated_list: '/api/proposals_paginated', // both for external and internal
    approvals_paginated_list: '/api/approvals_paginated',
    dcvpermits_paginated_list: '/api/dcvpermits_paginated',
    dcvadmissions_paginated_list: '/api/dcvadmissions_paginated',
    stickers_paginated_list: '/api/stickers_paginated',
    compliances_paginated_external: '/api/compliances_paginated/list_external',
    moorings_paginated_internal: '/api/moorings_paginated/list_internal',
    compliances:"/api/compliances.json",
    vessel_external_list: '/api/vessel/list_external',
    waitinglistapplication: '/api/waitinglistapplication/',
    waitinglistallocation: '/api/waitinglistallocation/',
    existing_mooring_licences: '/api/mooringlicence/existing_mooring_licences',
    existing_licences: '/api/approvals/existing_licences',
    annualadmissionapplication: '/api/annualadmissionapplication/',
    authoriseduserapplication: '/api/authoriseduserapplication/',
    mooringlicenceapplication: '/api/mooringlicenceapplication/',
    proposal: '/api/proposal/',
    approvals: '/api/approvals/',
    stickers: '/api/stickers/',
    holder_list: '/api/approvals/holder_list/',
    vessel: '/api/vessel/',
    mooring: '/api/mooring/',
    proposal_standard_requirements:"/api/proposal_standard_requirements.json",
    proposal_requirements:"/api/proposal_requirements.json",
    vesselownership: '/api/vesselownership/',
    proposal_by_uuid: '/api/proposal_by_uuid/',

    lookupVessel: function(id) {
        return `/api/vessel/${id}/lookup_vessel.json`;
    },
    lookupCompanyOwnership: function(id) {
        return `/api/company/${id}/lookup_company_ownership.json`;
    },
    lookupDcvVessel: function(id) {
        return `/api/dcv_vessel/${id}/lookup_dcv_vessel.json`;
    },
    lookupVesselOwnership: function(id) {
        return `/api/vesselownership/${id}/lookup_vessel_ownership.json`;
    },
    lookupIndividualOwnership: function(id) {
        return `/api/vessel/${id}/lookup_individual_ownership.json`;
    },

    discard_proposal: function (id) {
        return `/api/proposal/${id}.json`;
    },
    /*
    proposals_paginated_internal:   "/api/proposal_paginated/proposals_internal/?format=datatables",
    mooringlicensings: '/api/mooringlicensings/',
    participants: '/api/participants/participants_list',
    parks: '/api/parks/parks_list',
    campgrounds: '/api/campgrounds/campgrounds_list',
    camping_choices: '/api/mooringlicensings/camping_choices',
    filter_list: '/api/mooringlicensings/filter_list/',
    temporary_document: '/api/temporary_document/',
    admin_data: '/admin_data/',
    */
}
