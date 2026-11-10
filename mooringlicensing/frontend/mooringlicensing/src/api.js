
export default {
    application_types:"/api/application_types",
    application_types_dict:"/api/application_types_dict",
    application_categories:"/api/application_categories",
    application_categories_dict:"/api/application_categories_dict",
    application_statuses_dict:"/api/application_statuses_dict",
    wla_allowed:"/api/wla_allowed",
    current_season: "/api/current_season",
    applicants_dict: "/api/applicants_dict",
    vessel_types_dict:"/api/vessel_types_dict",
    insurance_choices_dict:"/api/insurance_choices_dict",
    vessel_rego_nos:"/api/vessel_rego_nos",
    mooring_lookup:"/api/mooring_lookup",
    mooring_lookup_by_site_licensee:"/api/mooring_lookup_by_site_licensee",
    mooring_lookup_per_bay:"/api/mooring_lookup_per_bay",
    vessel_lookup:"/api/vessel_lookup",
    sticker_lookup:"/api/sticker_lookup",
    person_lookup:"/api/person_lookup",
    company_names:"/api/company_names",
    dcv_vessel_rego_nos:"/api/dcv_vessel_rego_nos",
    fee_configurations: "/api/fee_configurations",
    approval_types_dict:"/api/approval_types_dict",
    approval_statuses_dict:"/api/approval_statuses_dict",
    payment_system_id: "/api/payment_system_id",
    fee_seasons_dict:"/api/fee_seasons_dict",
    sticker_status_dict: "/api/sticker_status_dict",
    sticker_non_exported_status_dict: "/api/sticker_non_exported_status_dict",
    compliance_statuses_dict:"/api/compliance_statuses_dict",
    mooring_statuses_dict:"/api/mooring_statuses_dict",
    mooring_bays:"/api/mooringbays.json",
    mooring_bays_lookup:"/api/mooringbays/lookup.json",
    seasons_for_dcv_dict: "/api/seasons_for_dcv_dict",
    daily_admission_url: "/api/daily_admission_url",
    dcv_organisations: "/api/dcv_organisations",
    fee_item_sticker_replacement: "/api/fee_item_sticker_replacement",

    profile: '/api/profile',
    users: '/api/users.json',
    filtered_users: '/api/filtered_users',
    countries: '/api/countries',

    proposals_paginated_list: '/api/proposals_paginated', // both for external and internal
    site_licensee_mooring_requests: '/api/site_licensee_mooring_requests_paginated',
    approvals_paginated_list: '/api/approvals_paginated',
    dcvpermits_paginated_list: '/api/dcvpermits_paginated',
    dcvadmissions_paginated_list: '/api/dcvadmissions_paginated',
    stickers_paginated_list: '/api/stickers_paginated',
    non_exported_stickers_paginated_list: '/api/non_exported_stickers_paginated',
    invoices_paginated_list: '/api/invoices_paginated',
    compliances_paginated: '/api/compliances_paginated',
    moorings_paginated: '/api/moorings_paginated',
    compliances:"/api/compliances.json",
    vessel_external_list: '/api/vessel/list_external',
    vessel_internal_list: '/api/vessel/list_internal',
    waitinglistapplication: '/api/waitinglistapplication/',
    internalwaitinglistapplication: '/api/internalwaitinglistapplication/',
    waitinglistallocation: '/api/waitinglistallocation/',
    existing_licences: '/api/approvals/existing_licences',
    annualadmissionapplication: '/api/annualadmissionapplication/',
    internalannualadmissionapplication: '/api/internalannualadmissionapplication/',
    authoriseduserapplication: '/api/authoriseduserapplication/',
    internalauthoriseduserapplication: '/api/internalauthoriseduserapplication/',
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
    temporary_document: '/api/temporary_document/',

    lookupApprovalDetails: function(id) {
        return `/api/approvals/${id}/lookup_approval.json`;
    },
    lookupApprovalHistory: function(id) {
        return `/api/approvals/${id}/approval_history?format=datatables`;
    },
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
}
