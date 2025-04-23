from django.shortcuts import render, redirect, get_object_or_404
from django.views import generic
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from .models import Event, Ticket, Category
from .forms import EventCreationForm, EventUpdateForm, CategoryForm

class EventListView(generic.ListView):
    model = Event
    template_name = 'event/event_list.html'
    paginate_by = 10

    def get_queryset(self):
        queryset = Event.objects.filter(is_public=True).order_by('start_date')
        query = self.request.GET.get('q')
        category = self.request.GET.get('category')

        if query:
            queryset = queryset.filter(Q(title__icontains=query) | Q(description__icontains=query) | Q(location__icontains=query))
        if category:
            queryset = queryset.filter(category__name=category)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        return context

class EventDetailView(generic.DetailView):
    model = Event
    template_name = 'event/event_detail.html'

@login_required
def event_register(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if event.capacity > event.ticket_set.count():
        Ticket.objects.get_or_create(user=request.user, event=event)
        return redirect('event_detail', pk=pk)
    else:
        # Gérer le cas où l'événement est complet
        return render(request, 'event/event_full.html', {'event': event})

class OrganizerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.role == 'organizer'

class EventCreateView(OrganizerRequiredMixin, generic.CreateView):
    model = Event
    form_class = EventCreationForm
    template_name = 'event/event_form.html'
    success_url = '/organizer/dashboard/'  # Rediriger vers le tableau de bord

    def form_valid(self, form):
        form.instance.organizer = self.request.user
        return super().form_valid(form)

class EventUpdateView(OrganizerRequiredMixin, generic.UpdateView):
    model = Event
    form_class = EventUpdateForm
    template_name = 'event/event_form.html'
    success_url = '/organizer/dashboard/'

    def get_queryset(self):
        return Event.objects.filter(organizer=self.request.user)

class EventDeleteView(OrganizerRequiredMixin, generic.DeleteView):
    model = Event
    template_name = 'event/event_confirm_delete.html'
    success_url = '/organizer/dashboard/'

    def get_queryset(self):
        return Event.objects.filter(organizer=self.request.user)

@login_required
def organizer_dashboard(request):
    events = Event.objects.filter(organizer=request.user)
    context = {'events': events}
    return render(request, 'event/organizer_dashboard.html', context)

@login_required
def event_participants(request, pk):
    event = get_object_or_404(Event, pk=pk, organizer=request.user)
    participants = Ticket.objects.filter(event=event).select_related('user')
    context = {'event': event, 'participants': participants}
    return render(request, 'event/event_participants.html', context)

@login_required
def create_category(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('event_list')  # Ou une autre page appropriée
    else:
        form = CategoryForm()
    return render(request, 'event/create_category.html', {'form': form})