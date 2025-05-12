from django.urls import path
from . import views

app_name = 'myevents'

urlpatterns = [
    path('', views.EventListView.as_view(), name='event_list'),
    path('event/<int:pk>/', views.EventDetailView.as_view(), name='event_detail'),
    path('event/new/', views.EventCreateView.as_view(), name='event_create'),
    path('event/<int:pk>/edit/', views.EventUpdateView.as_view(), name='event_update'),
    path('event/<int:pk>/delete/', views.EventDeleteView.as_view(), name='event_delete'),
    path('event/<int:pk>/purchase/', views.purchase_ticket, name='purchase_ticket'),
    path('organizer/dashboard/', views.organizer_dashboard, name='organizer_dashboard'),
    path('event/<int:pk>/register/', views.event_register, name='event_register'),
    path('organizer/event/<int:pk>/participants/', views.event_participants, name='event_participants'),
    path('event/<int:pk>/participants/export/csv/', views.export_participants_csv, name='export_participants_csv'),
    path('event/<int:pk>/participants/export/pdf/', views.export_participants_pdf, name='export_participants_pdf'),
    path('category/create/', views.create_category, name='create_category'),
    path('event/<int:pk>/statistics/', views.event_statistics, name='event_statistics'),
    path('event/<int:pk>/settings/', views.event_settings, name='event_settings'),
    path('event/<int:pk>/settings/notifications/', views.notification_settings, name='notification_settings'),
    path('event/<int:pk>/cancel/', views.event_cancel, name='event_cancel'),
]