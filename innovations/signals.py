from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Evaluation, Recommendation
from .services import build_recommendation_from_evaluation


@receiver(post_save, sender=Evaluation)
def create_system_recommendation(sender, instance, **kwargs):
    priority, text = build_recommendation_from_evaluation(instance)
    Recommendation.objects.update_or_create(
        based_on_evaluation=instance,
        defaults={
            'school': instance.school,
            'innovation': instance.innovation,
            'priority': priority,
            'status': Recommendation.Status.PENDING,
            'generated_by_system': True,
            'recommendation_text': text,
        },
    )
