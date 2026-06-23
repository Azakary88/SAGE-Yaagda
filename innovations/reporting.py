from io import BytesIO

from django.db.models import Avg, Count, Sum
from django.http import HttpResponse
from django.utils.html import escape
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image as ReportImage
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
        scope_name = first_school.name if first_school else "Votre école"
        scope_detail = (
            f"{first_school.ceb.name} | {first_school.province.name}"
            if first_school
            else "Zone d'action limitée à votre école."
        )
        return {
            'role': role,
            'level_label': 'École',
            'scope_name': scope_name,
            'scope_detail': scope_detail,
            'summary_title': "Rapports de suivi de votre école",
            'summary_intro': (
                "Préparez une synthèse détaillée sur une activité précise ou un rapport consolidé "
                "sur l'ensemble des activités déclarées par votre école."
            ),
        }

    if role == User.Role.PEDAGOGICAL_SUPERVISOR:
        ceb = getattr(user, 'ceb', None)
        scope_name = ceb.name if ceb else 'Votre CEB'
        scope_detail = ceb.province.name if ceb else "Zone d'action limitée aux écoles de votre CEB."
        return {
            'role': role,
            'level_label': 'CEB',
            'scope_name': scope_name,
            'scope_detail': scope_detail,
            'summary_title': "Rapports de suivi de la CEB",
            'summary_intro': (
                "Centralisez les activités déclarées par les écoles de votre CEB au moyen "
                "de synthèses détaillées ou de rapports consolidés."
            ),
        }

    if role == User.Role.PROVINCIAL_USER:
        province = getattr(user, 'province', None)
        scope_name = province.name if province else 'Votre province'
        scope_detail = province.region.name if province else "Zone d'action limitée aux CEB de votre province."
        return {
            'role': role,
            'level_label': 'Province',
            'scope_name': scope_name,
            'scope_detail': scope_detail,
            'summary_title': "Rapports de suivi de la province",
            'summary_intro': (
                "Consolidez les activités remontées par les CEB de votre province dans des "
                "rapports de pilotage et de synthèse."
            ),
        }

    if role == User.Role.REGIONAL_AGENT:
        region = getattr(user, 'region', None)
        scope_name = region.name if region else 'Votre région'
        scope_detail = "Toutes les provinces visibles de votre région."
        return {
            'role': role,
            'level_label': 'Région',
            'scope_name': scope_name,
            'scope_detail': scope_detail,
            'summary_title': 'Rapports régionaux de suivi',
            'summary_intro': (
                "Comparez les provinces de votre région et consolidez l'ensemble des "
                "activités remontées jusqu'au niveau des écoles."
            ),
        }

    return {
        'role': role,
        'level_label': 'Système',
        'scope_name': 'Ensemble des données visibles',
        'scope_detail': "Zone d'action globale de l'administration.",
        'summary_title': 'Rapports de suivi du système',
        'summary_intro': (
            "Produisez des rapports détaillés ou consolidés sur l'ensemble des activités "
            "accessibles à votre profil."
        ),
    }


def _general_comparison_definition(role):
    if role == User.Role.SCHOOL_DIRECTOR:
        return {
            'title': "Comparaison des innovations de l'école",
            'column_label': 'Innovation',
            'values': ['innovation__name'],
            'label': lambda row: row['innovation__name'],
        }
    if role == User.Role.PEDAGOGICAL_SUPERVISOR:
        return {
            'title': 'Comparaison des écoles de la CEB',
            'column_label': 'École',
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
        f"L'activité '{activity.title}' a été déclarée le {activity.reporting_date:%d/%m/%Y} "
        f"par l'école {activity.school.name} dans le cadre de l'innovation {activity.innovation.name}. "
        f"Elle a mobilisé {activity.participating_students} élève(s), {activity.trained_teachers} "
        f"enseignant(s) et {activity.taught_hours} heure(s) d'encadrement. "
        f"{media_total} média(s) et {recommendation_count} recommandation(s) sont associés à cette activité."
    )
    if avg_score is not None:
        text += f" Le score moyen d'évaluation disponible est de {avg_score}/100."
    return text


def _general_summary_text(metadata, activities_total, schools_total, media_total, avg_score):
    text = (
        f"La zone d'action '{metadata['scope_name']}' totalise {activities_total} activité(s) déclarée(s) dans "
        f"{schools_total} école(s), avec {media_total} média(s) justificatif(s) disponibles."
    )
    if avg_score is not None:
        text += f" Le score moyen des évaluations liées aux activités ressort à {avg_score}/100."
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
            'report_kind_label': "Synthèse détaillée d'une activité",
            'report_title': f"Rapport de synthèse - {activity.title}",
            'report_intro': "Fiche détaillée de l'activité, de ses justificatifs et des observations associées.",
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
                {'label': 'Élèves participants', 'value': activity.participating_students},
                {'label': 'Enseignants formés', 'value': activity.trained_teachers},
                {'label': 'Heures dispensées', 'value': activity.taught_hours},
                {'label': 'Ordinateurs utilisés', 'value': activity.computers_count},
                {'label': 'Images téléversées', 'value': media_total},
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
    media_items = list(
        ActivityMedia.objects.filter(activity__in=activity_queryset)
        .select_related(
            'activity',
            'activity__school',
            'activity__school__province',
            'activity__school__ceb',
            'uploaded_by',
        )
        .order_by('-created_at')
    )
    schools_total = activity_queryset.values('school_id').distinct().count()
    media_total = len(media_items)
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
        'report_kind_label': 'Rapport consolidé',
        'report_title': 'Rapport consolidé des activités',
        'report_intro': "Vue consolidée des activités accessibles à votre niveau de responsabilité.",
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
            {'label': 'Activités', 'value': aggregates['activities_total'] or 0},
            {'label': 'Écoles couvertes', 'value': schools_total},
            {'label': 'Innovations suivies', 'value': innovations_total},
            {'label': 'Enseignants formés', 'value': aggregates['teachers_total'] or 0},
            {'label': 'Images téléversées', 'value': media_total},
            {'label': 'Score moyen', 'value': f'{avg_score}/100' if avg_score is not None else 'N/D'},
        ],
        'activities': activities,
        'media_items': media_items,
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


def _build_media_gallery_table(media_items, styles, include_activity_context=False, columns=2):
    if not media_items:
        return None

    column_width = 8.1 * cm if columns == 2 else 5.2 * cm
    image_width = column_width - (0.8 * cm)
    image_height = 5.4 * cm if columns == 2 else 4.0 * cm
    gallery_cells = []

    for media in media_items:
        cell_rows = []
        try:
            image = ReportImage(media.file.path)
            image._restrictSize(image_width, image_height)
            cell_rows.append([image])
        except Exception:
            cell_rows.append([Paragraph("Image indisponible dans l'export PDF.", styles['Italic'])])

        meta_parts = [media.created_at.strftime('%d/%m/%Y %H:%M')]
        if include_activity_context:
            meta_parts.append(f"{media.activity.school.name} - {media.activity.title}")
        if media.uploaded_by:
            meta_parts.append(media.uploaded_by.get_full_name() or media.uploaded_by.username)

        caption = (
            f"<b>{escape(' | '.join(meta_parts))}</b><br/>"
            f"{escape(media.comment or 'Aucun commentaire.')}"
        )
        cell_rows.append([Paragraph(caption, styles['BodyText'])])

        cell = Table(cell_rows, colWidths=[column_width - (0.4 * cm)])
        cell.setStyle(
            TableStyle(
                [
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#d6e8db')),
                    ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ]
            )
        )
        gallery_cells.append(cell)

    gallery_rows = []
    for index in range(0, len(gallery_cells), columns):
        row = gallery_cells[index:index + columns]
        while len(row) < columns:
            row.append('')
        gallery_rows.append(row)

    gallery = Table(gallery_rows, colWidths=[column_width] * columns)
    gallery.setStyle(
        TableStyle(
            [
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]
        )
    )
    return gallery


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
        Paragraph("DREPPNF Yaagda - Rapport de suivi des activités", styles['Title']),
        Spacer(1, 0.2 * cm),
        Paragraph(report_context['report_title'], styles['Heading2']),
        Paragraph(report_context['report_intro'], styles['BodyText']),
        Spacer(1, 0.2 * cm),
        Paragraph(
            f"Zone d'action : {report_context['metadata']['level_label']} - {report_context['metadata']['scope_name']}",
            styles['BodyText'],
        ),
        Paragraph(report_context['metadata']['scope_detail'], styles['BodyText']),
        Paragraph(
            f"Date de génération : {report_context['generated_at'].strftime('%d/%m/%Y %H:%M')}",
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
            Paragraph('Indicateurs clés', styles['Heading2']),
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
            ['École', activity.school.name],
            ['Innovation', activity.innovation.name],
            ['Date de rapportage', activity.reporting_date.strftime('%d/%m/%Y')],
            ['Classes concernées', activity.classes_concerned or 'Non renseignées'],
            ['Internet disponible', 'Oui' if activity.has_internet else 'Non'],
            ['Description', activity.description or 'Aucune description saisie.'],
            ['Ressources disponibles', activity.available_resources or 'Aucune ressource renseignée.'],
            ['Contraintes', activity.challenges or 'Aucune contrainte signalée.'],
        ]
        story.extend(
            [
                Paragraph("Informations sur l'activité", styles['Heading2']),
                _build_table(details_rows, [5.0 * cm, 11.2 * cm]),
                Spacer(1, 0.3 * cm),
            ]
        )

        evaluation_rows = [['Date', 'Évaluateur', 'Score', 'Résultats observés']]
        for evaluation in report_context['evaluations']:
            evaluation_rows.append(
                [
                    evaluation.evaluation_date.strftime('%d/%m/%Y'),
                    evaluation.evaluator.get_full_name() or evaluation.evaluator.username if evaluation.evaluator else '-',
                    f"{_score(evaluation.performance_score)}/100",
                    Paragraph(evaluation.observed_results or 'Aucun détail fourni.', styles['BodyText']),
                ]
            )
        if len(evaluation_rows) == 1:
            evaluation_rows.append(['-', '-', '-', 'Aucune évaluation liée à cette activité.'])
        story.extend(
            [
                Paragraph('Évaluations liées', styles['Heading2']),
                _build_table(evaluation_rows, [2.4 * cm, 4.0 * cm, 2.0 * cm, 8.0 * cm]),
                Spacer(1, 0.3 * cm),
            ]
        )

        recommendation_rows = [['Date', 'Priorité', 'Recommandation']]
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
                Paragraph('Recommandations associées', styles['Heading2']),
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
            media_rows.append(['-', '-', 'Aucune image téléversée.', '-'])
        story.extend(
            [
                Paragraph('Pièces justificatives', styles['Heading2']),
                _build_table(media_rows, [3.0 * cm, 3.8 * cm, 6.4 * cm, 3.8 * cm]),
                Spacer(1, 0.25 * cm),
            ]
        )
        media_gallery = _build_media_gallery_table(report_context['media_items'], styles, include_activity_context=False)
        if media_gallery is not None:
            story.extend(
                [
                    Paragraph("Galerie des images de l'activité", styles['Heading2']),
                    media_gallery,
                ]
            )

        filename = f"rapport-activité-{activity.id}.pdf"
    else:
        innovation_rows = [['Innovation', 'Activités', 'Enseignants', 'Heures', 'Score moyen']]
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
                Paragraph('Synthèse par innovation', styles['Heading2']),
                _build_table(innovation_rows, [7.0 * cm, 3.0 * cm, 4.0 * cm, 3.0 * cm, 3.0 * cm]),
                Spacer(1, 0.3 * cm),
            ]
        )

        comparison_rows = [
            [
                report_context['comparison_column_label'],
                'Activités',
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
            comparison_rows.append(['Aucune donnée', '0', '0', 'N/D'])
        story.extend(
            [
                Paragraph(report_context['comparison_title'], styles['Heading2']),
                _build_table(comparison_rows, [11.0 * cm, 4.0 * cm, 3.5 * cm, 4.0 * cm]),
                Spacer(1, 0.3 * cm),
            ]
        )

        activity_rows = [['Date', 'Province', 'CEB', 'École', 'Innovation', 'Titre', 'Participants']]
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
            activity_rows.append(['-', '-', '-', 'Aucune activité visible.', '-', '-', '0'])
        story.extend(
            [
                Paragraph('Relevé détaillé des activités', styles['Heading2']),
                _build_table(activity_rows, [2.3 * cm, 3.4 * cm, 3.2 * cm, 4.3 * cm, 3.0 * cm, 7.0 * cm, 2.2 * cm]),
                Spacer(1, 0.3 * cm),
            ]
        )
        media_gallery = _build_media_gallery_table(
            report_context['media_items'],
            styles,
            include_activity_context=True,
            columns=3,
        )
        if media_gallery is not None:
            story.extend(
                [
                    Paragraph('Galerie des images justificatives', styles['Heading2']),
                    media_gallery,
                ]
            )

        filename = 'rapport-general-activités.pdf'

    document.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
