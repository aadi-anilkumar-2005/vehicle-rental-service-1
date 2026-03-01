from django.urls import path
from . import views

# URL configurations for the owner backend app
urlpatterns = [
    path('', views.login_view, name='owner_login'),
    path('login/', views.login_view, name='owner_login'),
    path('register/', views.register_view, name='owner_register'),
    path('dashboard/', views.dashboard_view, name='owner_dashboard'),
    path('staff/', views.staff_management_view, name='owner_staff'),
    path('vehicles/', views.vehicle_management_view, name='owner_vehicles'),
    path('bookings/', views.booking_management_view, name='owner_bookings'),
    path('chat/', views.chat_view, name='owner_chat'),
    path('reviews/', views.reviews_view, name='owner_reviews'),
    path('complaints/', views.complaints_view, name='owner_complaints'),
    path('kyc/', views.kyc_management_view, name='owner_kyc'),
    path('kyc/<int:kyc_id>/', views.kyc_detail_view, name='owner_kyc_detail'),
    path('profile/', views.profile_view, name='owner_profile'),
    path('logout/', views.logout_view, name='owner_logout'),
    path('api/staff/', views.staff_api, name='owner_staff_api'),
]
