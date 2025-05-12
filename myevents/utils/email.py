from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags

def send_event_confirmation_email(user, event, ticket):
    """Send confirmation email after successful event registration."""
    subject = f'Confirmation - {event.title}'
    html_message = render_to_string('myevents/emails/event_confirmation.html', {
        'user': user,
        'event': event,
        'ticket': ticket
    })
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message
    )

def send_ticket_purchase_email(user, ticket, payment):
    """Send email after successful ticket purchase."""
    subject = f'Ticket Purchase Confirmation - {ticket.event.title}'
    html_message = render_to_string('myevents/emails/ticket_purchase.html', {
        'user': user,
        'ticket': ticket,
        'payment': payment,
        'event': ticket.event
    })
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message
    )

def send_event_reminder_email(user, event, ticket):
    """Send reminder email 24 hours before the event."""
    subject = f'Reminder: {event.title} starts tomorrow!'
    html_message = render_to_string('myevents/emails/event_reminder.html', {
        'user': user,
        'event': event,
        'ticket': ticket
    })
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message
    )

def send_event_update_email(event, update_type='modified'):
    """Send email to all registered participants when an event is updated or cancelled."""
    subject = f'Event Update - {event.title}'
    participants = event.tickets.filter(status='confirmed').select_related('user')
    
    for ticket in participants:
        html_message = render_to_string('myevents/emails/event_update.html', {
            'user': ticket.user,
            'event': event,
            'ticket': ticket,
            'update_type': update_type
        })
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[ticket.user.email],
            html_message=html_message
        )
