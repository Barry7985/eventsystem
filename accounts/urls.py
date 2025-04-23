from django.urls import path
from .views import CustomLoginView, register, activate_account

urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
    path('register/', register, name='register'),
    path('activate/<str:token>/', activate_account, name='activate'),
]