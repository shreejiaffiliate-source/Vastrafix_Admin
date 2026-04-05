from requests import Response
from rest_framework import generics
from .models import Banner, Category, Item
from .serializers import BannerSerializer, CategorySerializer, ItemSerializer, SubcategorySerializer
from rest_framework.decorators import api_view
from .models import SubCategory
from .serializers import SubcategorySerializer
from rest_framework.permissions import IsAuthenticated
from .models import Item
from rest_framework.decorators import permission_classes
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from rest_framework.generics import ListAPIView
from .models import Complaint
from .serializers import ComplaintSerializer
from rest_framework import status
from django.shortcuts import get_object_or_404  
from orders.models import Order  # Order model ko import karna hoga


@api_view(['GET'])
def service_items(request):
    service_type = request.GET.get('type')  # Steam Iron
    qs = SubCategory.objects.filter(type__name=service_type, is_active=True)
    serializer = SubcategorySerializer(qs, many=True)
    return Response(serializer.data)

    
class SubCategoryByServiceView(APIView):
    def get(self, request):
        service_type = request.GET.get('type')

        subcategories = SubCategory.objects.filter(
            service__name=service_type,
            is_active=True
        )

        serializer = SubcategorySerializer(subcategories, many=True)
        return Response(serializer.data)


class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer


class ItemListView(generics.ListAPIView):
    queryset = Item.objects.filter(is_active=True)
    serializer_class = ItemSerializer    


#support and services views

from .models import Complaint
from .serializers import ComplaintSerializer

class RaiseComplaintView(generics.CreateAPIView):
    serializer_class = ComplaintSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        # Login user ko automatic assign karna
        serializer.save(user=self.request.user)
        
    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return Response({
            "success": True,
            "message": "Complaint submitted successfully.",
            "data": response.data
        }, status=status.HTTP_201_CREATED)    
        
class BannerListView(ListAPIView):
    queryset = Banner.objects.filter(is_active=True)
    serializer_class = BannerSerializer     


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_complaint(request):
    try:
        # 1. Text data extract karein (Multipart data POST me aata hai)
        order_id = request.POST.get('order')  # Flutter: fields['order']
        complaint_message = request.POST.get('message') # Flutter: fields['message']
        user_name = request.POST.get('user_name')
        subject = request.POST.get('subject')

        # 2. Image file extract karein (FILES me aati hai)
        # Flutter: request.files.add(..., 'image', ...)
        complaint_image = request.FILES.get('image') 

        # Validation
        if not order_id or not complaint_message:
            return Response(
                {"success": False, "message": "Order ID and message are required."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check karein ki order exist karta hai
        order = get_object_or_404(Order, id=order_id)

        # 3. Database mein save karein (Image field ke saath)
        complaint = Complaint.objects.create(
            order=order,
            user=request.user,
            issue="Order Service Issue",
            message=complaint_message,
            subject=subject if subject else f"Order Issue #{order_id}",
            # 🔥 Ye aapki image field honi chahiye model mein
            image=complaint_image  
        )

        return Response(
            {"success": True, "message": "Complaint submitted successfully with image."}, 
            status=status.HTTP_201_CREATED
        )

    except Exception as e:
        print(f"Error: {str(e)}") # Debugging ke liye
        return Response(
            {"success": False, "message": "Server error occurred."}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )      