from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse


def csrf_failure(request, reason="", template_name="errors/csrf_failure.html"):
    reason_key = reason.lower()
    if "incorrect" in reason_key:
        reason_message = (
            "Le jeton de sécurité associé au formulaire n'est plus valide. "
            "Cela arrive souvent après une reconnexion, un retour arrière du navigateur ou une page restée ouverte trop longtemps."
        )
    elif "cookie not set" in reason_key:
        reason_message = (
            "Le navigateur n'a pas transmis le cookie de sécurité nécessaire à la validation du formulaire."
        )
    elif "referer checking failed" in reason_key:
        reason_message = (
            "La vérification de provenance de la requête a échoué. "
            "Vérifiez que l'adresse de l'application est bien celle ouverte dans votre navigateur."
        )
    else:
        reason_message = (
            "La vérification de sécurité n'a pas pu être effectuée correctement pour cette demande."
        )

    if request.user.is_authenticated:
        fallback_url = reverse('dashboard:home')
    else:
        fallback_url = reverse('login')

    response = render(
        request,
        template_name,
        {
            'page_title': "Vérification de sécurité",
            'reason_message': reason_message,
            'retry_url': request.META.get('HTTP_REFERER') or fallback_url,
            'fallback_url': fallback_url,
        },
        status=403,
    )
    response['Cache-Control'] = 'no-store'
    return response


def healthcheck(request):
    return JsonResponse({'status': 'ok', 'service': 'SAGE YAADGA'})
