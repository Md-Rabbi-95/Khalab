# orders/signals.py
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.db import transaction
from .models import Order

@receiver(pre_save, sender=Order)
def order_status_changed(sender, instance, **kwargs):
    tracker = getattr(instance, "tracker", None)
    if tracker is None:
        return  # No tracker on this model; avoid AttributeError and let Order.save() handle emails.

    # If a tracker is present, keep old behavior (no-op here unless you previously emailed from signals).
    if tracker.has_changed("status"):
        # If you used to send email here, do it safely on commit:
        transaction.on_commit(lambda: instance.send_status_update_email())
