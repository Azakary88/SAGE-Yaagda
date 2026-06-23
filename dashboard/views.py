import json
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from accounts.models import User
from accounts.scopes import (
    filter_activities_for_user,
    filter_ceb_evaluations_for_user,
    filter_cebs_for_user,
    filter_evaluations_for_user,
    filter_province_evaluations_for_user,
    filter_provinces_for_user,
    filter_recommendations_for_user,
    filter_school_admin_evaluations_for_user,
    filter_schools_for_user,
    summarize_visible_scope,
)
from dashboard.ai import build_school_ai_analysis
from innovations.models import Activity, ActivityMedia, Evaluation, Recommendation
from innovations.services import build_priority_needs, top_performing_schools
from schools.models import CEB, Province, School


def _score(value):
    return round(float(value), 1) if value is not None else None


def _ai_titles_for_role(role):
    if role == User.Role.SCHOOL_DIRECTOR:
        return {
            'title': "Analyse IA de votre école",
            'subtitle': (
                "Le module d'analyse classe votre école selon le niveau de risque observé "
                "à partir des activités, des évaluations et des recommandations."
            ),
        }
    return {
        'title': "Analyse IA des écoles de votre zone d'action",
        'subtitle': (
            "Le module d'analyse regroupe les écoles par profils de risque et priorise "
            "les actions d'accompagnement."
        ),
    }


def _build_ai_detail_context(user, limit=50):
    role = User.Role.ADMINISTRATOR if user.is_superuser else user.role
    visible_schools = filter_schools_for_user(
        user,
        School.objects.select_related('province', 'province__region', 'ceb', 'director'),
    )
    ai_titles = _ai_titles_for_role(role)
    ai_analysis = build_school_ai_analysis(visible_schools, limit=limit)
    return {
        'role': role,
        'visible_schools': visible_schools,
        'visible_scope': summarize_visible_scope(user),
        'ai_analysis': ai_analysis,
        'ai_title': ai_titles['title'],
        'ai_subtitle': ai_titles['subtitle'],
    }


@login_required
def home(request):
    user = request.user
    role = User.Role.ADMINISTRATOR if user.is_superuser else user.role
    ai_context = _build_ai_detail_context(user, limit=8)

    visible_schools = filter_schools_for_user(
        user,
        School.objects.select_related('province', 'province__region', 'ceb', 'director'),
    )
    visible_activities = filter_activities_for_user(
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
    visible_recommendations = filter_recommendations_for_user(
        user,
        Recommendation.objects.select_related('school', 'school__province', 'innovation'),
    )
    visible_provinces = filter_provinces_for_user(
        user,
        Province.objects.select_related('region'),
    )
    visible_cebs = filter_cebs_for_user(
        user,
        CEB.objects.select_related('province', 'province__region'),
    )
    visible_scope = summarize_visible_scope(user)

    schools_total = visible_scope['schools']
    activities_total = visible_activities.count()
    innovation_evaluations_total = filter_evaluations_for_user(
        user,
        Evaluation.objects.select_related('school', 'innovation'),
    ).count()
    recommendations_total = visible_recommendations.count()
    schools_with_activity = visible_scope['schools_with_activity']
    coverage_rate = round((schools_with_activity / schools_total) * 100, 1) if schools_total else 0
    innovation_stats = list(
        visible_activities.values('innovation__name')
        .annotate(total=Count('id'))
        .order_by('-total', 'innovation__name')
    )

    context = {
        'visible_scope': visible_scope,
        'innovation_chart_labels': json.dumps([item['innovation__name'] for item in innovation_stats]),
        'innovation_chart_values': json.dumps([item['total'] for item in innovation_stats]),
        'recent_activities': visible_activities.order_by('-reporting_date', '-created_at')[:8],
        'recent_recommendations': visible_recommendations[:5],
        'recommendations_total': recommendations_total,
        'ai_analysis': ai_context['ai_analysis'],
        'ai_title': ai_context['ai_title'],
        'ai_subtitle': ai_context['ai_subtitle'],
    }

    if role in {User.Role.ADMINISTRATOR, User.Role.REGIONAL_AGENT}:
        province_rows = list(
            visible_provinces.annotate(
                total_cebs=Count('cebs', distinct=True),
                total_schools=Count('schools', distinct=True),
                total_activities=Count('schools__activities', distinct=True),
                avg_score=Avg('administrative_evaluations__performance_score'),
            ).order_by('name')
        )
        province_evaluations_total = filter_province_evaluations_for_user(user).values('province_id').distinct().count()
        context.update(
            {
                'dashboard_level': 'province',
                'dashboard_title': (
                    'Tableau de pilotage régional'
                    if role == User.Role.REGIONAL_AGENT
                    else 'Tableau de pilotage administrateur'
                ),
                'dashboard_intro': (
                    'Vision consolidée des provinces, des agents provinciaux et des activités '
                    "relevées dans l'ensemble de votre zone d'action."
                ),
                'primary_metric_label': 'Provinces suivies',
                'primary_metric_value': len(province_rows),
                'secondary_metric_label': 'Activités',
                'secondary_metric_value': activities_total,
                'tertiary_metric_label': 'Provinces évaluées',
                'tertiary_metric_value': province_evaluations_total,
                'quaternary_metric_label': 'Taux de couverture',
                'quaternary_metric_value': f'{coverage_rate}%',
                'comparison_title': 'Comparaison des provinces',
                'comparison_value_label': "Nombre d'activités",
                'comparison_score_label': 'Score moyen',
                'comparison_chart_labels': json.dumps([province.name for province in province_rows]),
                'comparison_chart_values': json.dumps(
                    [province.total_activities for province in province_rows],
                ),
                'comparison_chart_scores': json.dumps(
                    [_score(province.avg_score) or 0 for province in province_rows],
                ),
                'show_comparison_scores': True,
                'province_rows': province_rows,
                'show_school_performance_sections': True,
                'top_schools': top_performing_schools(limit=5, school_queryset=visible_schools),
                'priority_needs': build_priority_needs(limit=5, school_queryset=visible_schools),
            }
        )
    elif role == User.Role.PROVINCIAL_USER:
        ceb_rows = list(
            visible_cebs.annotate(
                total_schools=Count('schools', distinct=True),
                total_activities=Count('schools__activities', distinct=True),
                avg_score=Avg('administrative_evaluations__performance_score'),
            ).order_by('name')
        )
        ceb_evaluations_total = filter_ceb_evaluations_for_user(user).values('ceb_id').distinct().count()
        context.update(
            {
                'dashboard_level': 'ceb',
                'dashboard_title': 'Tableau de pilotage provincial',
                'dashboard_intro': (
                    'Vision consolidée des CEB de votre province, du suivi des encadreurs '
                    'pédagogiques et des évaluations administratives réalisées.'
                ),
                'primary_metric_label': 'CEB suivies',
                'primary_metric_value': len(ceb_rows),
                'secondary_metric_label': 'Activités',
                'secondary_metric_value': activities_total,
                'tertiary_metric_label': 'CEB évaluées',
                'tertiary_metric_value': ceb_evaluations_total,
                'quaternary_metric_label': 'Taux de couverture',
                'quaternary_metric_value': f'{coverage_rate}%',
                'comparison_title': 'Comparaison des CEB de la province',
                'comparison_value_label': "Nombre d'activités",
                'comparison_score_label': 'Score moyen',
                'comparison_chart_labels': json.dumps([ceb.name for ceb in ceb_rows]),
                'comparison_chart_values': json.dumps([ceb.total_activities for ceb in ceb_rows]),
                'comparison_chart_scores': json.dumps([_score(ceb.avg_score) or 0 for ceb in ceb_rows]),
                'show_comparison_scores': True,
                'ceb_rows': ceb_rows,
                'show_school_performance_sections': True,
                'top_schools': top_performing_schools(limit=5, school_queryset=visible_schools),
                'priority_needs': build_priority_needs(limit=5, school_queryset=visible_schools),
            }
        )
    elif role == User.Role.PEDAGOGICAL_SUPERVISOR:
        school_rows = list(
            visible_schools.annotate(
                total_activities=Count('activities', distinct=True),
                avg_score=Avg('administrative_evaluations__performance_score'),
                innovation_score=Avg('evaluations__performance_score'),
                media_total=Count('activities__media_items', distinct=True),
            ).order_by('name')
        )
        school_evaluations_total = filter_school_admin_evaluations_for_user(
            user,
        ).values('school_id').distinct().count()
        context.update(
            {
                'dashboard_level': 'school',
                'dashboard_title': 'Tableau de pilotage de la CEB',
                'dashboard_intro': (
                    "Vision consolidée des écoles de votre CEB, du suivi des directeurs "
                    "d'école et des évaluations administratives réalisées."
                ),
                'primary_metric_label': 'Écoles suivies',
                'primary_metric_value': len(school_rows),
                'secondary_metric_label': 'Activités',
                'secondary_metric_value': activities_total,
                'tertiary_metric_label': 'Écoles évaluées',
                'tertiary_metric_value': school_evaluations_total,
                'quaternary_metric_label': 'Taux de couverture',
                'quaternary_metric_value': f'{coverage_rate}%',
                'comparison_title': 'Comparaison des écoles de la CEB',
                'comparison_value_label': "Nombre d'activités",
                'comparison_score_label': 'Score administratif',
                'comparison_chart_labels': json.dumps([school.name for school in school_rows]),
                'comparison_chart_values': json.dumps(
                    [school.total_activities for school in school_rows],
                ),
                'comparison_chart_scores': json.dumps(
                    [_score(school.avg_score) or 0 for school in school_rows],
                ),
                'show_comparison_scores': True,
                'school_rows': school_rows,
                'show_school_performance_sections': False,
            }
        )
    else:
        director_school = visible_schools.first()
        director_activities = list(
            visible_activities.annotate(media_total=Count('media_items', distinct=True)).order_by(
                '-reporting_date',
                '-created_at',
            )
        )
        media_items = ActivityMedia.objects.filter(activity__in=visible_activities).select_related(
            'activity',
            'uploaded_by',
        )
        media_total = media_items.count()
        participants_total = visible_activities.aggregate(total=Sum('participating_students'))['total'] or 0
        context.update(
            {
                'dashboard_level': 'director',
                'dashboard_title': "Tableau de suivi du directeur d'école",
                'dashboard_intro': (
                    f"Suivi opérationnel des activités déclarées par {director_school.name}."
                    if director_school
                    else "Suivi opérationnel des activités déclarées par votre école."
                ),
                'primary_metric_label': 'Activités',
                'primary_metric_value': activities_total,
                'secondary_metric_label': 'Images téléversées',
                'secondary_metric_value': media_total,
                'tertiary_metric_label': 'Élèves touchés',
                'tertiary_metric_value': participants_total,
                'quaternary_metric_label': 'Évaluations innovation',
                'quaternary_metric_value': innovation_evaluations_total,
                'comparison_title': 'Répartition des activités par innovation',
                'comparison_value_label': "Nombre d'activités",
                'comparison_score_label': '',
                'comparison_chart_labels': json.dumps([item['innovation__name'] for item in innovation_stats]),
                'comparison_chart_values': json.dumps([item['total'] for item in innovation_stats]),
                'comparison_chart_scores': json.dumps([]),
                'show_comparison_scores': False,
                'director_school': director_school,
                'director_activities': director_activities,
                'latest_media': media_items.order_by('-created_at')[:6],
                'show_school_performance_sections': False,
            }
        )

    return render(request, 'dashboard/home.html', context)


@login_required
def ai_analysis(request):
    context = _build_ai_detail_context(request.user, limit=50)
    context['page_title'] = "Module d'analyse IA"
    context['page_intro'] = (
        "Consultez le fonctionnement du module intelligent, les scores de confiance "
        "et les priorités d'accompagnement proposées."
    )
    return render(request, 'dashboard/ai_analysis.html', context)


@login_required
def ai_analysis_pdf(request):
    context = _build_ai_detail_context(request.user, limit=50)
    ai_analysis = context['ai_analysis']

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph("DREPPNF Yaagda - Rapport d'analyse IA", styles['Title']),
        Spacer(1, 0.3 * cm),
        Paragraph(f"Zone d'action : {context['ai_title']}", styles['Heading2']),
        Paragraph(context['ai_subtitle'], styles['BodyText']),
        Spacer(1, 0.2 * cm),
        Paragraph(
            f"Date de génération : {timezone.localtime().strftime('%d/%m/%Y %H:%M')}",
            styles['BodyText'],
        ),
        Spacer(1, 0.4 * cm),
    ]

    summary = ai_analysis['summary']
    summary_table = Table(
        [
            ['Moteur', ai_analysis['engine_name']],
            ["Écoles analysées", str(summary['total_schools'])],
            ['Risque élevé', str(summary['high_risk'])],
            ['Suivi prioritaire', str(summary['monitored'])],
            ['Bonne dynamique', str(summary['healthy'])],
            ['Confiance moyenne', f"{summary.get('avg_confidence', 0)}/100"],
        ],
        colWidths=[5.2 * cm, 10.3 * cm],
    )
    summary_table.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]
        )
    )
    story.extend(
        [
            Paragraph("Synthèse de l'analyse", styles['Heading2']),
            summary_table,
            Spacer(1, 0.4 * cm),
        ]
    )

    if ai_analysis['enabled']:
        story.extend(
            [
                Paragraph('Présentation du modèle', styles['Heading2']),
                Paragraph(ai_analysis['methodology']['description'], styles['BodyText']),
                Paragraph(ai_analysis['methodology']['target'], styles['BodyText']),
                Paragraph(ai_analysis['methodology']['confidence_rule'], styles['BodyText']),
                Spacer(1, 0.2 * cm),
                Paragraph(
                    'Variables utilisées : ' + ', '.join(ai_analysis['methodology']['features']) + '.',
                    styles['BodyText'],
                ),
                Spacer(1, 0.4 * cm),
                Paragraph("Priorités identifiées", styles['Heading2']),
            ]
        )
    else:
        story.extend(
            [
                Paragraph('Présentation du modèle', styles['Heading2']),
                Paragraph(
                    "Le rapport ne contient pas encore suffisamment de données pour produire une analyse IA détaillée.",
                    styles['BodyText'],
                ),
                Spacer(1, 0.4 * cm),
            ]
        )

    insight_rows = [
        [
            'École',
            'Profil IA',
            'Risque',
            'Confiance',
            'Action recommandée',
        ]
    ]
    for insight in ai_analysis['insights'][:20]:
        insight_rows.append(
            [
                Paragraph(
                    f"{insight['school_name']}<br/><font size=8>{insight['province_name']} | {insight['ceb_name']}</font>",
                    styles['BodyText'],
                ),
                Paragraph(insight['profile_label'], styles['BodyText']),
                Paragraph(f"{insight['risk_score']}/100", styles['BodyText']),
                Paragraph(f"{insight['confidence_score']}/100", styles['BodyText']),
                Paragraph(insight['recommended_action'], styles['BodyText']),
            ]
        )

    if len(insight_rows) == 1:
        insight_rows.append(['Aucune école visible', '-', '-', '-', '-'])

    insights_table = Table(
        insight_rows,
        colWidths=[4.2 * cm, 2.5 * cm, 2.0 * cm, 2.2 * cm, 5.1 * cm],
        repeatRows=1,
    )
    insights_table.setStyle(
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
    story.append(insights_table)

    document.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="analyse-ia-dreppnf.pdf"'
    return response
