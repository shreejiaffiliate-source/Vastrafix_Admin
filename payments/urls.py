from django.urls import path
from .views import CreatePaymentView, UserPaymentListView

urlpatterns = [
    path('create/', CreatePaymentView.as_view(), name='create-payment'),
    path('my-payments/', UserPaymentListView.as_view(), name='my-payments'),
]
