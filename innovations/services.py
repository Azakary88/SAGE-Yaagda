from django.db.models import Avg, Count

from schools.models import School

from .models import Recommendation


def build_recommendation_from_evaluation(evaluation):
    score = float(evaluation.performance_score)

    if score < 40:
        priority = Recommendation.Priority.CRITICAL
        text = (
            "Renforcer en urgence cette innovation : appui pédagogique, dotation en "
            "ressources et suivi de proximité."
        )
    elif score < 60:
        priority = Recommendation.Priority.HIGH
        text = (
            "Programmer un accompagnement ciblé pour corriger les contraintes "
            "signalées et relancer la mise en œuvre."
        )
    elif score < 80:
        priority = Recommendation.Priority.MEDIUM
        text = (
            "Poursuivre l'encadrement et consolider les bonnes pratiques avant une "
            "extension à plus grande échelle."
        )
    else:
        priority = Recommendation.Priority.LOW
        text = (
            "Maintenir la dynamique actuelle et valoriser cette expérience comme "
            "référence pour les autres écoles."
        )

    return priority, text


def top_performing_schools(limit=5, school_queryset=None):
    school_queryset = school_queryset or School.objects.all()
    return (
        school_queryset.annotate(
            avg_score=Avg('evaluations__performance_score'),
            total_activities=Count('activities', distinct=True),
            total_evaluations=Count('evaluations', distinct=True),
        )
        .filter(total_evaluations__gt=0)
        .order_by('-avg_score', '-total_activities', 'name')[:limit]
    )


def build_priority_needs(limit=5, school_queryset=None):
    school_queryset = school_queryset or School.objects.all()
    ranked_schools = (
        school_queryset.annotate(
            avg_score=Avg('evaluations__performance_score'),
            total_activities=Count('activities', distinct=True),
            total_evaluations=Count('evaluations', distinct=True),
        )
        .order_by('avg_score', 'total_activities', 'name')
    )

    priorities = []
    for school in ranked_schools:
        reasons = []
        if school.total_activities == 0:
            reasons.append('aucune activité remontée')
        if school.total_evaluations == 0:
            reasons.append('aucune évaluation disponible')
        elif school.avg_score is not None and school.avg_score < 60:
            reasons.append('performance inférieure au seuil attendu')

        if reasons:
            priorities.append(
                {
                    'school': school,
                    'avg_score': school.avg_score,
                    'reasons': ', '.join(reasons),
                }
            )

        if len(priorities) >= limit:
            break

    return priorities
