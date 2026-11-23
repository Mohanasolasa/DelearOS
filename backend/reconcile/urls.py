from django.urls import path
from reconcile.api.views import DisagreementListView

urlpatterns = [
    path('disagreements/', DisagreementListView.as_view(), name='disagreement-list'),
]
