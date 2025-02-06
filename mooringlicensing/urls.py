from django.conf import settings
from django.contrib import admin
from django.urls import re_path, include
from django.conf.urls.static import static
from rest_framework import routers

from mooringlicensing import views
from mooringlicensing.components.approvals.views import DcvAdmissionFormView
from mooringlicensing.components.payments_ml.views import (
    ApplicationFeeView, ApplicationFeeSuccessView, 
    DcvPermitFeeView, DcvPermitFeeSuccessView, DcvPermitPDFView, 
    ConfirmationView, DcvAdmissionFeeView, 
    DcvAdmissionFeeSuccessView, DcvAdmissionPDFView, ApplicationFeeExistingView, 
    StickerReplacementFeeView, 
    StickerReplacementFeeSuccessView, ApplicationFeeAlreadyPaid, 
    ApplicationFeeSuccessViewPreload, DcvPermitFeeSuccessViewPreload, 
    DcvAdmissionFeeSuccessViewPreload, 
    StickerReplacementFeeSuccessViewPreload
)
from mooringlicensing.components.payments_ml import api as payments_api
from mooringlicensing.components.proposals import api as proposal_api
from mooringlicensing.components.approvals import api as approval_api
from mooringlicensing.components.compliances import api as compliances_api
from mooringlicensing.components.proposals.views import (
    AuthorisedUserApplicationEndorseView, 
    MooringLicenceApplicationDocumentsUploadView
)
from mooringlicensing.components.users import api as users_api
from mooringlicensing.components.main import api as main_api
from ledger_api_client.urls import urlpatterns as ledger_patterns

# API patterns
from mooringlicensing.management.default_data_manager import DefaultDataManager
from mooringlicensing.settings import PRIVATE_MEDIA_DIR_NAME
from mooringlicensing.utils import are_migrations_running
from django.urls import path

router = routers.DefaultRouter()
router.include_root_view = settings.SHOW_API_ROOT
router.register(r'proposal', proposal_api.ProposalViewSet, 'proposal')
router.register(r'proposal_by_uuid', proposal_api.ProposalByUuidViewSet, 'proposal_by_uuid')
router.register(r'waitinglistapplication', proposal_api.WaitingListApplicationViewSet, 'waitinglistapplication')
router.register(r'annualadmissionapplication', proposal_api.AnnualAdmissionApplicationViewSet, 'annualadmissionapplication')
router.register(r'authoriseduserapplication', proposal_api.AuthorisedUserApplicationViewSet, 'authoriseduserapplication')

router.register(r'internalwaitinglistapplication', proposal_api.InternalWaitingListApplicationViewSet, 'internalwaitinglistapplication')
router.register(r'internalannualadmissionapplication', proposal_api.InternalAnnualAdmissionApplicationViewSet, 'internalannualadmissionapplication')
router.register(r'internalauthoriseduserapplication', proposal_api.InternalAuthorisedUserApplicationViewSet, 'internalauthoriseduserapplication')

router.register(r'mooringlicenceapplication', proposal_api.MooringLicenceApplicationViewSet, 'mooringlicenceapplication')
router.register(r'site_licensee_mooring_requests_paginated', proposal_api.SiteLicenseeMooringRequestPaginatedViewSet,'site_licensee_mooring_requests_paginated')
router.register(r'proposals_paginated', proposal_api.ProposalPaginatedViewSet, 'proposals_paginated')
router.register(r'approvals_paginated', approval_api.ApprovalPaginatedViewSet, 'approvals_paginated')
router.register(r'dcvpermits_paginated', approval_api.DcvPermitPaginatedViewSet, 'dcvpermits_paginated')
router.register(r'dcvadmissions_paginated', approval_api.DcvAdmissionPaginatedViewSet, 'dcvadmissions_paginated')
router.register(r'stickers_paginated', approval_api.StickerPaginatedViewSet, 'stickers_paginated')
router.register(r'stickers', approval_api.StickerViewSet, 'stickers')
router.register(r'compliances_paginated', compliances_api.CompliancePaginatedViewSet, 'compliances_paginated')
router.register(r'moorings_paginated', proposal_api.MooringPaginatedViewSet, 'moorings_paginated')
router.register(r'approvals', approval_api.ApprovalViewSet, 'approvals')
router.register(r'waitinglistallocation', approval_api.WaitingListAllocationViewSet, 'waitinglistallocation')
router.register(r'compliances', compliances_api.ComplianceViewSet, 'compliances')
router.register(r'proposal_requirements', proposal_api.ProposalRequirementViewSet, 'proposal_requirements')
router.register(r'proposal_standard_requirements', proposal_api.ProposalStandardRequirementViewSet, 'proposal_standard_requirements')
router.register(r'users', users_api.UserViewSet, 'users')
router.register(r'amendment_request', proposal_api.AmendmentRequestViewSet, 'amendment_request')
router.register(r'compliance_amendment_request', compliances_api.ComplianceAmendmentRequestViewSet, 'compliance_amendment_request')
router.register(r'mooringbays', proposal_api.MooringBayViewSet, 'mooringbays')
router.register(r'vessel', proposal_api.VesselViewSet, 'vessel')
router.register(r'mooring', proposal_api.MooringViewSet, 'mooring')
router.register(r'dcv_vessel', approval_api.DcvVesselViewSet, 'dcv_vessel')
router.register(r'vesselownership', proposal_api.VesselOwnershipViewSet, 'vesselownership')
router.register(r'dcv_permit', approval_api.DcvPermitViewSet, 'dcv_permit')
router.register(r'internal_dcv_permit', approval_api.InternalDcvPermitViewSet, 'internal_dcv_permit')
router.register(r'dcv_admission', approval_api.DcvAdmissionViewSet, 'dcv_admission')
router.register(r'internal_dcv_admission', approval_api.InternalDcvAdmissionViewSet, 'internal_dcv_admission')
router.register(r'company', proposal_api.CompanyViewSet, 'company')
router.register(r'companyownership', proposal_api.CompanyOwnershipViewSet, 'companyownership')

api_patterns = [
    re_path(r'^api/profile$', users_api.GetProfile.as_view(), name='get-profile'),
    re_path(r'^api/profile/(?P<proposal_pk>\d+)$', users_api.GetProposalApplicantUser.as_view(), name='get-proposal-applicant-user'),
    re_path(r'^api/countries$', users_api.GetCountries.as_view(), name='get-countries'),
    re_path(r'^api/application_types$', proposal_api.GetApplicationTypeDescriptions.as_view(), name='get-application-type-descriptions'),
    re_path(r'^api/application_types_dict$', proposal_api.GetApplicationTypeDict.as_view(), name='get-application-type-dict'),
    re_path(r'^api/application_categories_dict$', proposal_api.GetApplicationCategoryDict.as_view(), name='get-application-category-dict'),
    re_path(r'^api/payment_system_id$', proposal_api.GetPaymentSystemId.as_view(), name='get-payment-system-id'),
    re_path(r'^api/fee_item_sticker_replacement$', proposal_api.GetStickerReplacementFeeItem.as_view(), name='get-sticker-replacement-fee-item'),
    re_path(r'^api/vessel_rego_nos$', proposal_api.GetVesselRegoNos.as_view(), name='get-vessel_rego-nos'),
    re_path(r'^api/mooring_lookup$', proposal_api.GetMooring.as_view(), name='get-mooring'),
    re_path(r'^api/mooring_lookup_by_site_licensee$', proposal_api.GetMooringBySiteLicensee.as_view(), name='get-mooring-lookup-by-site-licensee'),
    re_path(r'^api/mooring_lookup_per_bay$', proposal_api.GetMooringPerBay.as_view(), name='get-mooring-per-bay'),
    re_path(r'^api/vessel_lookup$', proposal_api.GetVessel.as_view(), name='get-vessel'),
    re_path(r'^api/sticker_lookup$', approval_api.GetSticker.as_view(), name='get-sticker'),
    re_path(r'^api/person_lookup$', users_api.GetPerson.as_view(), name='get-person'),
    re_path(r'^api/company_names$', proposal_api.GetCompanyNames.as_view(), name='get-company-names'),
    re_path(r'^api/dcv_vessel_rego_nos$', proposal_api.GetDcvVesselRegoNos.as_view(), name='get-dcv-vessel_rego-nos'),
    re_path(r'^api/dcv_organisations$', proposal_api.GetDcvOrganisations.as_view(), name='get-dcv-organisations'),
    re_path(r'^api/fee_configurations$', payments_api.GetFeeConfigurations.as_view(), name='get-fee-configurations'),
    re_path(r'^api/vessel_types_dict$', proposal_api.GetVesselTypesDict.as_view(), name='get-vessel-types-dict'),
    re_path(r'^api/insurance_choices_dict$', proposal_api.GetInsuranceChoicesDict.as_view(), name='get-insurance-choices-dict'),
    re_path(r'^api/application_statuses_dict$', proposal_api.GetApplicationStatusesDict.as_view(), name='get-application-statuses-dict'),
    re_path(r'^api/approval_types_dict$', approval_api.GetApprovalTypeDict.as_view(), name='get-approval-type-dict'),
    re_path(r'^api/wla_allowed$', approval_api.GetWlaAllowed.as_view(), name='get-wla-allowed'),
    re_path(r'^api/current_season$', approval_api.GetCurrentSeason.as_view(), name='get-current-season'),
    re_path(r'^api/approval_statuses_dict$', approval_api.GetApprovalStatusesDict.as_view(), name='get-approval-statuses-dict'),
    re_path(r'^api/fee_seasons_dict$', approval_api.GetFeeSeasonsDict.as_view(), name='get-fee-seasons-dict'),
    re_path(r'^api/sticker_status_dict$', approval_api.GetStickerStatusDict.as_view(), name='get-sticker-status-dict'),
    re_path(r'^api/daily_admission_url$', approval_api.GetDailyAdmissionUrl.as_view(), name='get-daily-admission-url'),
    re_path(r'^api/seasons_for_dcv_dict$', payments_api.GetSeasonsForDcvPermitDict.as_view(), name='get-approval-statuses-dict'),
    re_path(r'^api/compliance_statuses_dict$', compliances_api.GetComplianceStatusesDict.as_view(), name='get-compliance-statuses-dict'),
    re_path(r'^api/mooring_statuses_dict$', proposal_api.GetMooringStatusesDict.as_view(), name='get-mooring-statuses-dict'),
    re_path(r'^api/',include(router.urls)),
    re_path(r'^api/amendment_request_reason_choices',proposal_api.AmendmentRequestReasonChoicesView.as_view(),name='amendment_request_reason_choices'),
    re_path(r'^api/compliance_amendment_reason_choices',compliances_api.ComplianceAmendmentReasonChoicesView.as_view(),name='amendment_request_reason_choices'),
    re_path(r'^api/external_dashboard_sections_list/$',main_api.GetExternalDashboardSectionsList.as_view(), name='get-external-dashboard-sections-list'),
]

# URL Patterns
urlpatterns = [
    path(r"admin/", admin.site.urls),
    re_path(r'^chaining/', include('smart_selects.urls')),
    re_path(r'', include(api_patterns)),
    re_path(r'^$', views.MooringLicensingRoutingView.as_view(), name='home'),
    re_path(r'^contact/', views.MooringLicensingContactView.as_view(), name='ds_contact'),
    re_path(r'^further_info/', views.MooringLicensingFurtherInformationView.as_view(), name='ds_further_info'),
    re_path(r'^internal/', views.InternalView.as_view(), name='internal'),
    re_path(r'^external/', views.ExternalView.as_view(), name='external'),
    re_path(r'^account/$', views.ExternalView.as_view(), name='manage-account'),
    re_path(r'^profiles/', views.ExternalView.as_view(), name='manage-profiles'),
    re_path(r'^mgt-commands/$', views.ManagementCommandsView.as_view(), name='mgt-commands'),
    re_path(r'^login-success/$', views.LoginSuccess.as_view(), name='login-success'),

    # payment related urls
    re_path(r'^application_fee/(?P<proposal_pk>\d+)/$', ApplicationFeeView.as_view(), name='application_fee'),
    re_path(r'^application_fee_existing/(?P<invoice_reference>\d+)/$', ApplicationFeeExistingView.as_view(), name='application_fee_existing'),
    re_path(r'^application_fee_already_paid/(?P<proposal_pk>\d+)/$', ApplicationFeeAlreadyPaid.as_view(), name='application_fee_already_paid'),
    re_path(r'^confirmation/(?P<proposal_pk>\d+)/$', ConfirmationView.as_view(), name='confirmation'),
    re_path(r'^success/fee/(?P<uuid>.+)/$', ApplicationFeeSuccessView.as_view(), name='fee_success'),
    re_path(r"ledger-api-success-callback/(?P<uuid>.+)/", ApplicationFeeSuccessViewPreload.as_view(), name="ledger-api-success-callback",),
    re_path(r'^dcv_permit_fee/(?P<dcv_permit_pk>\d+)/$', DcvPermitFeeView.as_view(), name='dcv_permit_fee'),
    re_path(r'^dcv_permit_success/(?P<uuid>.+)/$', DcvPermitFeeSuccessView.as_view(), name='dcv_permit_fee_success'),
    re_path(r'^dcv_permit_success_preload/(?P<uuid>.+)/$', DcvPermitFeeSuccessViewPreload.as_view(), name='dcv_permit_fee_success_preload'),
    re_path(r'^dcv_admission_fee/(?P<dcv_admission_pk>\d+)/$', DcvAdmissionFeeView.as_view(), name='dcv_admission_fee'),
    re_path(r'^dcv_admission_success/(?P<uuid>.+)/$', DcvAdmissionFeeSuccessView.as_view(), name='dcv_admission_fee_success'),
    re_path(r'^dcv_admission_success_preload/(?P<uuid>.+)/$', DcvAdmissionFeeSuccessViewPreload.as_view(), name='dcv_admission_fee_success_preload'),
    re_path(r'^sticker_replacement_fee/$', StickerReplacementFeeView.as_view(), name='sticker_replacement_fee'),
    re_path(r'^sticker_replacement_fee_success/(?P<uuid>.+)/$', StickerReplacementFeeSuccessView.as_view(), name='sticker_replacement_fee_success'),
    re_path(r'^sticker_replacement_fee_success_preload/(?P<uuid>.+)/$', StickerReplacementFeeSuccessViewPreload.as_view(), name='sticker_replacement_fee_success_preload'),
    re_path(r'^aua_for_endorsement/(?P<uuid_str>[a-zA-Z0-9-]+)/view/$', AuthorisedUserApplicationEndorseView.as_view(), {'action': 'view'}, name='view-url'),
    re_path(r'^aua_for_endorsement/(?P<uuid_str>[a-zA-Z0-9-]+)/endorse/$', AuthorisedUserApplicationEndorseView.as_view(), {'action': 'endorse'}, name='endorse-url'),
    re_path(r'^aua_for_endorsement/(?P<uuid_str>[a-zA-Z0-9-]+)/decline/$', AuthorisedUserApplicationEndorseView.as_view(), {'action': 'decline'}, name='decline-url'),
    re_path(r'^mla_documents_upload/(?P<uuid_str>[a-zA-Z0-9-]+)/$', MooringLicenceApplicationDocumentsUploadView.as_view(), name='mla-documents-upload'),
    re_path(r'^dcv_admission_form/$', DcvAdmissionFormView.as_view(), name='dcv_admission_form'),
    re_path(r'payments/dcv-permit-pdf/(?P<id>\d+)', DcvPermitPDFView.as_view(), name='dcv-permit-pdf'),
    re_path(r'payments/dcv-admission-pdf/(?P<id>\d+)', DcvAdmissionPDFView.as_view(), name='dcv-admission-pdf'),

    #following url is defined so that to include url path when sending Proposal amendment request to user.
    re_path(r'^external/proposal/(?P<proposal_pk>\d+)/$', views.ExternalProposalView.as_view(), name='external-proposal-detail'),
    re_path(r'^internal/proposal/(?P<proposal_pk>\d+)/$', views.InternalProposalView.as_view(), name='internal-proposal-detail'),
    re_path(r'^external/compliance/(?P<compliance_pk>\d+)/$', views.ExternalComplianceView.as_view(), name='external-compliance-detail'),
    re_path(r'^internal/compliance/(?P<compliance_pk>\d+)/$', views.InternalComplianceView.as_view(), name='internal-compliance-detail'),

    re_path(r'^private-media/', views.getPrivateFile, name='view_private_file'),
] + ledger_patterns 



if settings.DEBUG:  # Serve media locally in development.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if not are_migrations_running():
    DefaultDataManager()

admin.site.site_header = "RIA Mooring Licensing System Administration"
admin.site.site_title = "RIA Mooring Licensing Site"
admin.site.index_title = "RIA Mooring Licensing"