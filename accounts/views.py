from django.contrib.auth import login, authenticate
from django.contrib.auth.views import LoginView
from django.shortcuts import render, redirect
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse, reverse_lazy
from django.contrib import messages
import uuid

from accounts.models import CustomUser
from .forms import CustomUserCreationForm

class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    
    def get_success_url(self):
        return reverse_lazy('acceuil')  # Redirect to 'acceuil' after login

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False  # Ensure user is inactive until activation
            user.activation_token = str(uuid.uuid4())
            user.save()
            
            # Send activation email
            activation_link = request.build_absolute_uri(
                reverse('activate', args=[user.activation_token]))
            send_mail(
                'Activez votre compte',
                f'Cliquez sur ce lien pour activer votre compte: {activation_link}',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            
            messages.success(request, 'Compte créé avec succès! Veuillez vérifier votre email pour activer votre compte.')
            return redirect('login')
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})

def activate_account(request, token):
    try:
        user = CustomUser.objects.get(activation_token=token)
        if not user.is_active:  # Only activate if not already active
            user.is_active = True
            user.activation_token = ''  # Clear the token after use
            user.save()
            messages.success(request, 'Votre compte a été activé avec succès! Vous pouvez maintenant vous connecter.')
        else:
            messages.info(request, 'Ce compte a déjà été activé.')
        return redirect('login')
    except CustomUser.DoesNotExist:
        messages.error(request, 'Le lien d\'activation est invalide!')
        
        return redirect('register')