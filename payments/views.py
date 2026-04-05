from rest_framework import generics, permissions
from .models import Payment
from .serializers import PaymentSerializer
from orders.models import Order


class CreatePaymentView(generics.CreateAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        order = serializer.validated_data['order']
        serializer.save(
            user=self.request.user,
            amount=order.total_amount,
            status='success' if serializer.validated_data['payment_method'] == 'cash' else 'pending'
        )


class UserPaymentListView(generics.ListAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user)

