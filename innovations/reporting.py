from io import BytesIO

from django.db.models import Avg, Count, Sum
from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from accounts.models import User
from accounts.scopes import filter_activities_for_user, filter_recommendations_for_user, filter_schools_for_user
from schools.models import School

from .forms import ActivityReportForm
from .models import Activity, ActivityMedia, Evaluation, Recommendation


def _role_for(user):
    return User.Role.ADMINISTRATOR if user.is_superuser else user.role


def _score(value):
    return round(float(value), 1) if value is not None else None


def _visible_activities(user):
    return filter_activities_for_user(
        user,
        Activity.objects.select_related(
            'school',
            'school__province',
            'school__province__region',
            'school__ceb',
            'innovation',
            'created_by',
        ),
    )


def _scope_metadata(user):
    role = _role_for(user)
    visible_schools = filter_schools_for_user(
        user,
        School.objects.select_related('province', 'province__region', 'ceb', 'director'),
    )
    first_school = visible_schools.first()

    if role == User.Role.SCHOOL_DIRECTOR:
        scope_name = first_school.name if first_school else "Votre ecole"
        scope_detail = (
            f"{first_school.ceb.name} | {first_school.province.name}"
            if first_school
            else "Perimetre limite a votre ecole."
        )
        return {
            'role': role,
            'level_label': 'Ecole',
            'scope_name': scope_name,
            'scope_detail': scope_detail,
            'summary_title': "Rapports de suivi de votre ecole",
            'summary_intro': (
                "Preparez une synthese detaillee sur une activite precise ou un rapport consolide "
                "sur l'ensemble des activites declarees par votre ecole."
            ),
        }

    if role == User.Role.PEDAGOGICAL_SUPERVISOR:
        ceb = getattr(user, 'ceb', None)
        scope_name = ceb.name if ceb else 'Votre CEB'
        scope_detail = ceb.province.name if ceb else "Perimetre limite aux ecoles de votre CEB."
        return {
            'role': role,
            'level_label': 'CEB',
            'scope_name': scope_name,
            'scope_detail': scope_detail,
            'summary_title': "Rapports de suivi de la CEB",
            'summary_intro': (
                "Centralisez les activites declarees par les ecoles de votre CEB au moyen "
                "de syntheses detaillees ou de rapports consolides."
            ),
        }

    if role == User.Role.PROVINCIAL_USER:
        province = getattr(user, 'province', None)
        scope_name = province.name if province else 'Votre province'
        scope_detail = province.region.name if province else "Perimetre limite aux CEB de votre province."
        return {
            'role': role,
            'level_label': 'Province',
            'scope_name': scope_name,
            'scope_detail': scope_detail,
            'summary_title': "Rapports de suivi de la province",
            'summary_intro': (
                "Consolidez les activites remontees par les CEB de votre province dans des "
                "rapports de pilotage et de synthese."
            ),
        }

    if role == User.Role.REGIONAL_AGENT:
        region = getattr(user, 'region', None)
        scope_name = region.name if region else 'Votre region'
        scope_detail = "Toutes les provinces visibles de votre region."
        return {
            'role': role,
            'level_label': 'Region',
            'scope_name': scope_name,
            'scope_detail': scope_detail,
            'summary_title': 'Rapports regionaux de suivi',
            'summary_intro': (
                "Comparez les provinces de votre region et consolidez l'ensemble des "
                "activites remontees jusqu'au niveau des ecoles."
            ),
        }

    return {
        'role': role,
        'level_label': 'Systeme',
        'scope_name': 'Ensemble des donnees visibles',
        'scope_detail': "Perimetre global de l'administration.",
        'summary_title': 'Rapports de suivi du systeme',
        'summary_intro': (
            "Produisez des rapports detailes ou consolides sur l'ensemble des activites "
            "accessibles a votre profil."
        ),
    }


def _general_comparison_definition(role):
    if role == User.Role.SCHOOL_DIRECTOR:
        return {
            'title': "Comparaison des innovations de l'ecole",
            'column_label': 'Innovation',
            'values': ['innovation__name'],
            'label': lambda row: row['innovation__name'],
        }
    if role == User.Role.PEDAGOGICAL_SUPERVISOR:
        return {
            'title': 'Comparaison des ecoles de la CEB',
            'column_label': 'Ecole',
            'values': ['school__code', 'school__name'],
            'label': lambda row: f"{row['school__name']} ({row['school__code']})",
        }
    if role == User.Role.PROVINCIAL_USER:
        return {
            'title': 'Comparaison des CEB de la province',
            'column_label': 'CEB',
            'values': ['school__ceb__code', 'school__ceb__name'],
            'label': lambda row: f"{row['school__ceb__name']} ({row['school__ceb__code']})",
        }
    return {
        'title': 'Comparaison des provinces',
        'column_label': 'Province',
        'values': ['school__province__code', 'school__province__name'],
        'label': lambda row: f"{row['school__province__name']} ({row['school__province__code']})",
    }


def _activity_summary_text(activity, media_total, avg_score, recommendation_count):
    text = (
        f"L'activite '{activity.title}' a ete declaree le {activity.reporting_date:%d/%m/%Y} "
        f"par l'ecole {activity.school.name} dans le cadre de l'innovation {activity.innovation.name}. "
        f"Elle a mobilise {activity.participating_students} eleve(s), {activity.trained_teachers} "
        f"enseignant(s) et {activity.taught_hours} heure(s) d'encadrement. "
        f"{media_total} media(s) et {recommendation_count} recommandation(s) sont associes a cette activite."
    )
    if avg_score is not None:
        text += f" Le score moyen d'evaluation disponible est de {avg_score}/100."
    return text


def _general_summary_text(metadata, activities_total, schools_total, media_total, avg_score):
    text = (
        f"Le perimetre '{metadata['scope_name']}' totalise {activities_total} activite(s) declarees dans "
        f"{schools_total} ecole(s), avec {media_total} media(s) justificatif(s) disponibles."
    )
    if avg_score is not None:
        text += f" Le score moyen des evaluations liees aux activites ressort a {avg_score}/100."
    return text


def build_activity_report_context(user, cleaned_data):
    report_kind = cleaned_data['report_kind']
    metadata = _scope_metadata(user)
    base_activities = _visible_activities(user)
    generated_at = timezone.localtime()

    if report_kind == ActivityReportForm.ReportKind.ACTIVITY:
        activity = base_activities.get(pk=cleaned_data['activity'].pk)
        media_items = list(activity.media_items.select_related('uploaded_by').order_by('-created_at'))
        evaluations = list(activity.evaluations.select_related('evaluator').order_by('-evaluation_date', '-id'))
        recommendations = list(
            filter_recommendations_for_user(
                user,
                Recommendation.objects.filter(
                    school_id=activity.school_id,
                    innovation_id=activity.innovation_id,
                ).order_by('-created_at'),
            )
        )
        avg_score = _score(
            activity.evaluations.aggregate(avg_score=Avg('performance_score'))['avg_score']
        )
        media_total = len(media_items)

        return {
            'report_kind': report_kind,
            'report_kind_label': "Synthese detaillee d'une activite",
            'report_title': f"Rapport de synthese - {activity.title}",
            'report_intro': "Fiche detaillee de l'activite, de ses justificatifs et des observations associees.",
            'metadata': metadata,
            'generated_at': generated_at,
            'activity': activity,
            'summary_text': _activity_summary_text(
                activity,
                media_total=media_total,
                avg_score=avg_score,
                recommendation_count=len(recommendations),
            ),
            'metrics': [
                {'label': 'Eleves participants', 'value': activity.participating_students},
                {'label': 'Enseignants formes', 'value': activity.trained_teachers},
                {'label': 'Heures dispensees', 'value': activity.taught_hours},
                {'label': 'Ordinateurs utilises', 'value': activity.computers_count},
                {'label': 'Images televersees', 'value': media_total},
                {'label': 'Score moyen', 'value': f'{avg_score}/100' if avg_score is not None else 'N/D'},
            ],
            'media_items': media_items,
            'evaluations': evaluations,
            'recommendations': recommendations,
        }

    activities = list(
        base_activities.annotate(
            media_total=Count('media_items', distinct=True),
            evaluation_total=Count('evaluations', distinct=True),
            avg_score=Avg('evaluations__performance_score'),
        ).order_by('-reporting_date', '-created_at')
    )
    activity_queryset = base_activities
    schools_total = activity_queryset.values('school_id').distinct().count()
    media_total = ActivityMedia.objects.filter(activity__in=activity_queryset).count()
    evaluations_queryset = Evaluation.objects.filter(activity__in=activity_queryset)
    recommendations_total = filter_recommendations_for_user(
        user,
        Recommendation.objects.filter(school__in=filter_schools_for_user(user, School.objects.all())),
    ).count()
    innovations_total = activity_queryset.values('innovation_id').distinct().count()
    aggregates = activity_queryset.aggregate(
        activities_total=Count('id'),
        teachers_total=Sum('trained_teachers'),
        hours_total=Sum('taught_hours'),
        computers_total=Sum('computers_count'),
    )
    avg_score = _score(evaluations_queryset.aggregate(avg_score=Avg('performance_score'))['avg_score'])

    innovation_rows = list(
        activity_queryset.values('innovation__name')
        .annotate(
            total_activities=Count('id'),
            total_teachers=Sum('trained_teachers'),
            total_hours=Sum('taught_hours'),
            avg_score=Avg('evaluations__performance_score'),
        )
        .order_by('-total_activities', 'innovation__name')
    )

    comparison_definition = _general_comparison_definition(metadata['role'])
    comparison_rows = list(
        activity_queryset.values(*comparison_definition['values'])
        .annotate(
            total_activities=Count('id'),
            total_media=Count('media_items', distinct=True),
            avg_score=Avg('evaluations__performance_score'),
        )
        .order_by('-total_activities')
    )
    for row in comparison_rows:
        row['label'] = comparison_definition['label'](row)

    return {
        'report_kind': report_kind,
        'report_kind_label': 'Rapport consolide',
        'report_title': 'Rapport consolide des activites',
        'report_intro': "Vue consolidee des activites accessibles a votre niveau de responsabilite.",
        'metadata': metadata,
        'generated_at': generated_at,
        'summary_text': _general_summary_text(
            metadata,
            activities_total=aggregates['activities_total'] or 0,
            schools_total=schools_total,
            media_total=media_total,
            avg_score=avg_score,
        ),
        'metrics': [
            {'label': 'Activites', 'value': aggregates['activities_total'] or 0},
            {'label': 'Ecoles couvertes', 'value': schools_total},
            {'label': 'Innovations suivies', 'value': innovations_total},
            {'label': 'Enseignants formes', 'value': aggregates['teachers_total'] or 0},
            {'label': 'Images televersees', 'value': media_total},
            {'label': 'Score moyen', 'value': f'{avg_score}/100' if avg_score is not None else 'N/D'},
        ],
        'activities': activities,
        'innovation_rows': innovation_rows,
        'comparison_title': comparison_definition['title'],
        'comparison_column_label': comparison_definition['column_label'],
        'comparison_rows': comparison_rows,
        'recommendations_total': recommendations_total,
        'evaluations_total': evaluations_queryset.count(),
        'hours_total': aggregates['hours_total'] or 0,
        'computers_total': aggregates['computers_total'] or 0,
    }


def _build_table(rows, col_widths):
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#198754')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def build_activity_report_pdf_response(report_context):
    is_activity_report = report_context['report_kind'] == ActivityReportForm.ReportKind.ACTIVITY
    pagesize = A4 if is_activity_report else landscape(A4)

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        leftMargin=1.4 * cm,
        rightMargin=1.4 * cm,
        topMargin=1.1 * cm,
        bottomMargin=1.1 * cm,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph('DREPPNF Yaagda - Rapport de suivi des activites', styles['Title']),
        Spacer(1, 0.2 * cm),
        Paragraph(report_context['report_title'], styles['Heading2']),
        Paragraph(report_context['report_intro'], styles['BodyText']),
        Spacer(1, 0.2 * cm),
        Paragraph(
            f"Perimetre : {report_context['metadata']['level_label']} - {report_context['metadata']['scope_name']}",
            styles['BodyText'],
        ),
        Paragraph(report_context['metadata']['scope_detail'], styles['BodyText']),
        Paragraph(
            f"Date de generation : {report_context['generated_at'].strftime('%d/%m/%Y %H:%M')}",
            styles['BodyText'],
        ),
        Spacer(1, 0.3 * cm),
        Paragraph(report_context['summary_text'], styles['BodyText']),
        Spacer(1, 0.3 * cm),
    ]

    metrics_rows = [['Indicateur', 'Valeur']]
    for metric in report_context['metrics']:
        metrics_rows.append([metric['label'], str(metric['value'])])
    story.extend(
        [
            Paragraph('Indicateurs cles', styles['Heading2']),
            _build_table(metrics_rows, [8.2 * cm, 7.0 * cm] if is_activity_report else [10.0 * cm, 12.0 * cm]),
            Spacer(1, 0.3 * cm),
        ]
    )

    if is_activity_report:
        activity = report_context['activity']
        details_rows = [
            ['Champ', 'Valeur'],
            ['Province', activity.school.province.name],
            ['CEB', activity.school.ceb.name],
            ['Ecole', activity.school.name],
            ['Innovation', activity.innovation.name],
            ['Date de rapportage', activity.reporting_date.strftime('%d/%m/%Y')],
            ['Classes concernees', activity.classes_concerned or 'Non renseignees'],
            ['Internet disponible', 'Oui' if activity.has_internet else 'Non'],
            ['Description', activity.description or 'Aucune description saisie.'],
            ['Ressources disponibles', activity.available_resources or 'Aucune ressource renseignee.'],
            ['Contraintes', activity.challenges or 'Aucune contrainte signalee.'],
        ]
        story.extend(
            [
                Paragraph("Informations sur l'activite", styles['Heading2']),
                _build_table(details_rows, [5.0 * cm, 11.2 * cm]),
                Spacer(1, 0.3 * cm),
            ]
        )

        evaluation_rows = [['Date', 'Evaluateur', 'Score', 'Resultats observes']]
        for evaluation in report_context['evaluations']:
            evaluation_rows.append(
                [
                    evaluation.evaluation_date.strftime('%d/%m/%Y'),
                    evaluation.evaluator.get_full_name() or evaluation.evaluator.username if evaluation.evaluator else '-',
                    f"{_score(evaluation.performance_score)}/100",
                    Paragraph(evaluation.observed_results or 'Aucun detail fourni.', styles['BodyText']),
                ]
            )
        if len(evaluation_rows) == 1:
            evaluation_rows.append(['-', '-', '-', 'Aucune evaluation liee a cette activite.'])
        story.extend(
            [
                Paragraph('Evaluations liees', styles['Heading2']),
                _build_table(evaluation_rows, [2.4 * cm, 4.0 * cm, 2.0 * cm, 8.0 * cm]),
                Spacer(1, 0.3 * cm),
            ]
        )

        recommendation_rows = [['Date', 'Priorite', 'Recommandation']]
        for recommendation in report_context['recommendations']:
            recommendation_rows.append(
                [
                    recommendation.created_at.strftime('%d/%m/%Y'),
                    recommendation.get_priority_display(),
                    Paragraph(recommendation.recommendation_text, styles['BodyText']),
                ]
            )
        if len(recommendation_rows) == 1:
            recommendation_rows.append(['-', '-', 'Aucune recommandation disponible.'])
        story.extend(
            [
                Paragraph('Recommandations associees', styles['Heading2']),
                _build_table(recommendation_rows, [2.6 * cm, 3.0 * cm, 10.8 * cm]),
                Spacer(1, 0.3 * cm),
            ]
        )

        media_rows = [['Date', 'Auteur', 'Commentaire', 'Fichier']]
        for media in report_context['media_items']:
            media_rows.append(
                [
                    media.created_at.strftime('%d/%m/%Y %H:%M'),
                    media.uploaded_by.get_full_name() or media.uploaded_by.username if media.uploaded_by else '-',
                    Paragraph(media.comment or 'Aucun commentaire.', styles['BodyText']),
                    media.file.name,
                ]
            )
        if len(media_rows) == 1:
            media_rows.append(['-', '-', 'Aucune image televersee.', '-'])
        story.extend(
            [
                Paragraph('Pieces justificatives', styles['Heading2']),
                _build_table(media_rows, [3.0 * cm, 3.8 * cm, 6.4 * cm, 3.8 * cm]),
            ]
        )

        filename = f"rapport-activite-{activity.id}.pdf"
    else:
        innovation_rows = [['Innovation', 'Activites', 'Enseignants', 'Heures', 'Score moyen']]
        for row in report_context['innovation_rows']:
            innovation_rows.append(
                [
                    row['innovation__name'],
                    str(row['total_activities']),
                    str(row['total_teachers'] or 0),
                    str(row['total_hours'] or 0),
                    f"{_score(row['avg_score'])}/100" if row['avg_score'] is not None else 'N/D',
                ]
            )
        if len(innovation_rows) == 1:
            innovation_rows.append(['Aucune innovation', '0', '0', '0', 'N/D'])
        story.extend(
            [
                Paragraph('Synthese par innovation', styles['Heading2']),
                _build_table(innovation_rows, [7.0 * cm, 3.0 * cm, 4.0 * cm, 3.0 * cm, 3.0 * cm]),
                Spacer(1, 0.3 * cm),
            ]
        )

        comparison_rows = [
            [
                report_context['comparison_column_label'],
                'Activites',
                'Images',
                'Score moyen',
            ]
        ]
        for row in report_context['comparison_rows']:
            comparison_rows.append(
                [
                    row['label'],
                    str(row['total_activities']),
                    str(row['total_media'] or 0),
                    f"{_score(row['avg_score'])}/100" if row['avg_score'] is not None else 'N/D',
                ]
            )
        if len(comparison_rows) == 1:
            comparison_rows.append(['Aucune donnee', '0', '0', 'N/D'])
        story.extend(
            [
                Paragraph(report_context['comparison_title'], styles['Heading2']),
                _build_table(comparison_rows, [11.0 * cm, 4.0 * cm, 3.5 * cm, 4.0 * cm]),
                Spacer(1, 0.3 * cm),
            ]
        )

        activity_rows = [['Date', 'Province', 'CEB', 'Ecole', 'Innovation', 'Titre', 'Participants']]
        for activity in report_context['activities']:
            activity_rows.append(
                [
                    activity.reporting_date.strftime('%d/%m/%Y'),
                    activity.school.province.name,
                    activity.school.ceb.name,
                    Paragraph(activity.school.name, styles['BodyText']),
                    activity.innovation.name,
                    Paragraph(activity.title, styles['BodyText']),
                    str(activity.participating_students),
                ]
            )
        if len(activity_rows) == 1:
            activity_rows.append(['-', '-', '-', 'Aucune activite visible.', '-', '-', '0'])
        story.extend(
            [
                Paragraph('Releve detaille des activites', styles['Heading2']),
                _build_table(activity_rows, [2.3 * cm, 3.4 * cm, 3.2 * cm, 4.3 * cm, 3.0 * cm, 7.0 * cm, 2.2 * cm]),
            ]
        )

        filename = 'rapport-general-activites.pdf'

    document.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
