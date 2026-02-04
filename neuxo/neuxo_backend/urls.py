from django.urls import path  # noqa: F401

from neuxo_backend.services import company_services

# ----------------------------- Main Functions -----------------------------------#
urlpatterns = [
    path(
        "matching/companies",
        company_services.getMatchingCompany,
        name="get_matching_companies",
    ),
]
