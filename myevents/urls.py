from django.urls import path
from . import views

urlpatterns = [
    path('', views.EventListView.as_view(), name='event_list'),
    path('event/<int:pk>/', views.EventDetailView.as_view(), name='event_detail'),
    path('event/<int:pk>/register/', views.event_register, name='event_register'),
    path('organizer/dashboard/', views.organizer_dashboard, name='organizer_dashboard'),
    path('organizer/event/create/', views.EventCreateView.as_view(), name='event_create'),
    path('organizer/event/<int:pk>/update/', views.EventUpdateView.as_view(), name='event_update'),
    path('organizer/event/<int:pk>/delete/', views.EventDeleteView.as_view(), name='event_delete'),
    path('organizer/event/<int:pk>/participants/', views.event_participants, name='event_participants'),
    path('category/create/', views.create_category, name='create_category'),
]