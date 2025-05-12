from django.shortcuts import render, redirect, get_object_or_404
from django.views import generic
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .utils.email import (
    send_event_confirmation_email,
    send_ticket_purchase_email,
    send_event_reminder_email,
    send_event_update_email
)
from django.db.models import Q, Sum
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponse
import csv
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

from .models import Event, Ticket, Category
from payment.models import Payment
from .forms import CategoryForm, EventForm, TicketForm

class EventListView(generic.ListView):
    model = Event
    template_name = 'myevents/event_list.html'
    context_object_name = 'events'
    paginate_by = 9

    def get_queryset(self):
        queryset = Event.objects.filter(
            status='published',
            start_date__gte=timezone.now()
        ).order_by('start_date')

        # Filter by category
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category__name=category)

        # Search functionality
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(location__icontains=search_query)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        return context


class EventDetailView(generic.DetailView):
    model = Event
    template_name = 'myevents/event_detail.html'
    context_object_name = 'event'

    def get_queryset(self):
        return Event.objects.filter(is_public=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context['has_ticket'] = Ticket.objects.filter(
                event=self.object,
                user=self.request.user,
                status='confirmed'
            ).exists()
        return context

@login_required
def event_register(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if event.capacity > event.ticket_set.count():
        ticket, created = Ticket.objects.get_or_create(user=request.user, event=event)
        if created:
            # Send confirmation email
            send_event_confirmation_email(request.user, event, ticket)
            messages.success(request, 'Registration successful! Check your email for confirmation.')
        return redirect('event_detail', pk=pk)
    else:
        # Gérer le cas où l'événement est complet
        messages.error(request, 'Sorry, this event is full.')
        return render(request, 'myevents/event_full.html', {'event': event})

class OrganizerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.role == 'organizer'

class EventCreateView(LoginRequiredMixin, UserPassesTestMixin, generic.CreateView):
    model = Event
    form_class = EventForm
    template_name = 'myevents/event_form.html'
    success_url = reverse_lazy('event_list')

    def test_func(self):
        return self.request.user.is_organizer

    def form_valid(self, form):
        form.instance.organizer = self.request.user
        messages.success(self.request, 'Event created successfully!')
        return super().form_valid(form)

class EventUpdateView(LoginRequiredMixin, UserPassesTestMixin, generic.UpdateView):
    model = Event
    form_class = EventForm
    template_name = 'myevents/event_form.html'
    success_url = reverse_lazy('event_list')

    def test_func(self):
        event = self.get_object()
        return self.request.user == event.organizer

    def form_valid(self, form):
        response = super().form_valid(form)
        # Send update notification to all registered participants
        send_event_update_email(self.object, update_type='modified')
        messages.success(self.request, 'Event updated successfully! Participants have been notified.')
        return response

class EventDeleteView(LoginRequiredMixin, UserPassesTestMixin, generic.DeleteView):
    model = Event
    template_name = 'myevents/event_confirm_delete.html'
    success_url = reverse_lazy('event_list')

    def test_func(self):
        event = self.get_object()
        return self.request.user == event.organizer

    def delete(self, request, *args, **kwargs):
        event = self.get_object()
        # Send cancellation notification to all registered participants
        send_event_update_email(event, update_type='cancelled')
        messages.success(request, 'Event cancelled successfully! Participants have been notified.')
        return super().delete(request, *args, **kwargs)

@login_required
def purchase_ticket(request, pk):
    event = get_object_or_404(Event, pk=pk)
    
    if request.method == 'POST':
        form = TicketForm(request.POST)
        if form.is_valid():
            # Check if there are available tickets
            if event.available_tickets > 0:
                ticket = form.save(commit=False)
                ticket.event = event
                ticket.user = request.user
                ticket.save()

                # Generate QR code
                ticket.generate_qr_code()

                # If the event is paid, create a payment
                if event.price > 0:
                    payment = Payment.objects.create(
                        ticket=ticket,
                        amount=event.price,
                        payment_method='stripe'  # This will be updated with actual payment method
                    )
                    # Send ticket purchase confirmation email
                    send_ticket_purchase_email(request.user, ticket, payment)
                    messages.success(request, 'Payment successful! Check your email for the ticket details.')
                    # Redirect to payment page
                    return redirect('payment_process', payment_id=payment.id)
                else:
                    ticket.status = 'confirmed'
                    ticket.save()
                    messages.success(request, 'Ticket purchased successfully!')
                    return redirect('ticket_detail', pk=ticket.pk)
            else:
                messages.error(request, 'Sorry, this event is sold out!')
    else:
        form = TicketForm()

    return render(request, 'myevents/purchase_ticket.html', {
        'form': form,
        'event': event
    })

#
# 
# @login_required
@login_required
def organizer_dashboard(request):
    """Vue pour le tableau de bord de l'organisateur."""
    user = request.user
    if not user.is_organizer:
        messages.error(request, "Vous n'avez pas les droits d'accès à cette page.")
        return redirect('home')

    # Récupérer les événements de l'organisateur
    events = Event.objects.filter(organizer=user)
    
    # Statistiques globales
    total_events = events.count()
    upcoming_events = events.filter(start_date__gte=timezone.now()).count()
    past_events = events.filter(end_date__lt=timezone.now()).count()
    
    # Statistiques des ventes
    total_tickets = Ticket.objects.filter(event__in=events).count()
    total_revenue = Ticket.objects.filter(event__in=events, is_paid=True).aggregate(
        total=Sum('event__price'))['total'] or 0
    
    # Événements à venir
    upcoming_events_list = events.filter(start_date__gte=timezone.now()).order_by('start_date')[:5]
    
    # Événements passés
    past_events_list = events.filter(end_date__lt=timezone.now()).order_by('-end_date')[:5]

    context = {
        'total_events': total_events,
        'upcoming_events': upcoming_events,
        'past_events': past_events,
        'total_tickets': total_tickets,
        'total_revenue': total_revenue,
        'upcoming_events_list': upcoming_events_list,
        'past_events_list': past_events_list,
    }
    
    return render(request, 'myevents/organizer/dashboard.html', context)

@login_required
def event_participants(request, pk):
    """Vue pour la liste des participants d'un événement."""
    event = get_object_or_404(Event, pk=pk)
    
    # Vérifier que l'utilisateur est l'organisateur
    if request.user != event.organizer:
        messages.error(request, "Vous n'avez pas les droits d'accès à cette page.")
        return redirect('home')
    
    # Récupérer les participants avec pagination
    participants = Ticket.objects.filter(event=event).select_related('user').order_by('-created_at')
    paginator = Paginator(participants, 10)
    page = request.GET.get('page')
    participants = paginator.get_page(page)
    
    context = {
        'event': event,
        'participants': participants,
    }
    
    return render(request, 'myevents/organizer/participants.html', context)

@login_required
def create_category(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('event_list')  # Ou une autre page appropriée
    else:
        form = CategoryForm()
    return render(request, 'myevents/create_category.html', {'form': form})

@login_required
def export_participants_csv(request, pk):
    """Vue pour exporter la liste des participants en CSV."""
    event = get_object_or_404(Event, pk=pk)
    
    # Vérifier que l'utilisateur est l'organisateur
    if request.user != event.organizer:
        messages.error(request, "Vous n'avez pas les droits d'accès à cette page.")
        return redirect('home')
    
    # Créer la réponse HTTP avec le type de contenu CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="participants_{event.slug}_{datetime.now().strftime("%Y%m%d")}.csv"'
    
    # Créer le writer CSV
    writer = csv.writer(response)
    
    # Écrire l'en-tête
    writer.writerow(['Nom', 'Email', 'Statut du billet', 'Date d\'achat', 'Statut du paiement', 'Numéro de billet'])
    
    # Écrire les données
    tickets = Ticket.objects.filter(event=event).select_related('user')
    for ticket in tickets:
        writer.writerow([
            ticket.user.get_full_name() or ticket.user.email,
            ticket.user.email,
            ticket.status,
            ticket.created_at.strftime('%d/%m/%Y %H:%M'),
            'Payé' if ticket.is_paid else 'En attente',
            ticket.ticket_number,
        ])
    
    return response

@login_required
def export_participants_pdf(request, pk):
    """Vue pour exporter la liste des participants en PDF."""
    event = get_object_or_404(Event, pk=pk)
    
    # Vérifier que l'utilisateur est l'organisateur
    if request.user != event.organizer:
        messages.error(request, "Vous n'avez pas les droits d'accès à cette page.")
        return redirect('home')
    
    # Créer la réponse HTTP avec le type de contenu PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="participants_{event.slug}_{datetime.now().strftime("%Y%m%d")}.pdf"'
    
    # Créer le document PDF
    doc = SimpleDocTemplate(response, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []
    
    # Ajouter le titre
    elements.append(Paragraph(f"Liste des participants - {event.title}", styles['Title']))
    elements.append(Paragraph("<br/><br/>", styles['Normal']))
    
    # Ajouter les informations de l'événement
    elements.append(Paragraph(f"Date: {event.start_date.strftime('%d/%m/%Y')}", styles['Normal']))
    elements.append(Paragraph(f"Lieu: {event.location}", styles['Normal']))
    elements.append(Paragraph("<br/><br/>", styles['Normal']))
    
    # Préparer les données du tableau
    data = [['Nom', 'Email', 'Statut', 'Date d\'achat', 'Paiement', 'N° Billet']]
    
    tickets = Ticket.objects.filter(event=event).select_related('user')
    for ticket in tickets:
        data.append([
            ticket.user.get_full_name() or ticket.user.email,
            ticket.user.email,
            ticket.status,
            ticket.created_at.strftime('%d/%m/%Y'),
            'Payé' if ticket.is_paid else 'En attente',
            ticket.ticket_number,
        ])
    
    # Créer le tableau
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(table)
    
    # Générer le PDF
    doc.build(elements)
    
    return response

@login_required
def event_statistics(request, pk):
    """Vue pour les statistiques d'un événement."""
    event = get_object_or_404(Event, pk=pk)
    
    # Vérifier que l'utilisateur est l'organisateur
    if request.user != event.organizer:
        messages.error(request, "Vous n'avez pas les droits d'accès à cette page.")
        return redirect('home')
    
    # Statistiques de base
    total_tickets = Ticket.objects.filter(event=event).count()
    total_sales = Ticket.objects.filter(event=event, is_paid=True).aggregate(
        total=Sum('event__price'))['total'] or 0
    average_price = event.price
    occupancy_rate = (total_tickets / event.capacity * 100) if event.capacity > 0 else 0
    
    # Données pour les graphiques
    # Ventes dans le temps
    sales_data = []
    sales_dates = []
    start_date = event.created_at
    end_date = timezone.now()
    current_date = start_date
    
    while current_date <= end_date:
        next_date = current_date + timedelta(days=1)
        daily_sales = Ticket.objects.filter(
            event=event,
            created_at__gte=current_date,
            created_at__lt=next_date,
            is_paid=True
        ).aggregate(total=Sum('event__price'))['total'] or 0
        
        sales_data.append(float(daily_sales))
        sales_dates.append(current_date.strftime('%d/%m/%Y'))
        current_date = next_date
    
    # Distribution des statuts
    status_data = [
        Ticket.objects.filter(event=event, status='confirmed').count(),
        Ticket.objects.filter(event=event, status='pending').count(),
        Ticket.objects.filter(event=event, status='cancelled').count(),
    ]
    
    # Méthodes de paiement (à adapter selon votre système de paiement)
    payment_methods = ['Carte bancaire', 'PayPal', 'Virement']
    payment_data = [70, 20, 10]  # Exemple de données
    
    # Distribution géographique (à adapter selon vos besoins)
    geo_locations = ['Paris', 'Lyon', 'Marseille', 'Bordeaux', 'Lille']
    geo_data = [40, 25, 15, 12, 8]  # Exemple de données
    
    context = {
        'event': event,
        'total_sales': total_sales,
        'total_tickets': total_tickets,
        'average_price': average_price,
        'occupancy_rate': round(occupancy_rate, 1),
        'sales_data': json.dumps(sales_data),
        'sales_dates': json.dumps(sales_dates),
        'status_data': json.dumps(status_data),
        'payment_methods': json.dumps(payment_methods),
        'payment_data': json.dumps(payment_data),
        'geo_locations': json.dumps(geo_locations),
        'geo_data': json.dumps(geo_data),
    }
    
    return render(request, 'myevents/organizer/statistics.html', context)

@login_required
def event_settings(request, pk):
    """Vue pour les paramètres d'un événement."""
    event = get_object_or_404(Event, pk=pk)
    
    # Vérifier que l'utilisateur est l'organisateur
    if request.user != event.organizer:
        messages.error(request, "Vous n'avez pas les droits d'accès à cette page.")
        return redirect('home')
    
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, "Les paramètres de l'événement ont été mis à jour.")
            return redirect('myevents:event_settings', pk=event.pk)
    else:
        form = EventForm(instance=event)
    
    # Récupérer les catégories pour le formulaire
    categories = Category.objects.all()
    
    # Récupérer les paramètres de notification (à adapter selon votre système)
    settings = {
        'notify_new_registration': True,
        'notify_payment': True,
        'notify_cancellation': True,
        'notification_email': request.user.email,
    }
    
    context = {
        'event': event,
        'form': form,
        'categories': categories,
        'settings': settings,
    }
    
    return render(request, 'myevents/organizer/settings.html', context)

@login_required
def notification_settings(request, pk):
    """Vue pour gérer les paramètres de notification d'un événement."""
    event = get_object_or_404(Event, pk=pk)
    
    # Vérifier que l'utilisateur est l'organisateur
    if request.user != event.organizer:
        messages.error(request, "Vous n'avez pas les droits d'accès à cette page.")
        return redirect('home')
    
    if request.method == 'POST':
        # Traiter les paramètres de notification (à adapter selon votre système)
        notify_new_registration = request.POST.get('notify_new_registration') == 'on'
        notify_payment = request.POST.get('notify_payment') == 'on'
        notify_cancellation = request.POST.get('notify_cancellation') == 'on'
        notification_email = request.POST.get('notification_email')
        
        # Sauvegarder les paramètres (à adapter selon votre système)
        # ...
        
        messages.success(request, "Les paramètres de notification ont été mis à jour.")
        return redirect('myevents:event_settings', pk=event.pk)
    
    return redirect('myevents:event_settings', pk=event.pk)

@login_required
def event_cancel(request, pk):
    """Vue pour annuler un événement."""
    event = get_object_or_404(Event, pk=pk)
    
    # Vérifier que l'utilisateur est l'organisateur
    if request.user != event.organizer:
        messages.error(request, "Vous n'avez pas les droits d'accès à cette page.")
        return redirect('home')
    
    if request.method == 'POST':
        # Marquer l'événement comme annulé
        event.status = 'cancelled'
        event.save()
        
        # Annuler tous les billets
        tickets = Ticket.objects.filter(event=event, status='confirmed')
        for ticket in tickets:
            ticket.status = 'cancelled'
            ticket.save()
            
            # Envoyer une notification au participant (à adapter selon votre système)
            # ...
            
            # Rembourser le billet (à adapter selon votre système de paiement)
            # ...
        
        messages.success(request, "L'événement a été annulé avec succès.")
        return redirect('myevents:organizer_dashboard')
    
    return redirect('myevents:event_settings', pk=event.pk)