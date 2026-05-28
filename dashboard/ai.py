from __future__ import annotations

from dataclasses import dataclass
import json

import numpy as np
from django.db.models import Avg, Count, Q, Sum

from schools.models import School

try:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    SKLEARN_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised implicitly when sklearn is unavailable.
    KMeans = None
    StandardScaler = None
    SKLEARN_AVAILABLE = False


@dataclass
class SchoolFeatureRow:
    school: School
    school_name: str
    province_name: str
    ceb_name: str
    total_activities: int
    total_recommendations: int
    high_recommendations: int
    critical_recommendations: int
    media_total: int
    total_participants: int
    total_trained_teachers: int
    internet_enabled_activities: int
    total_innovation_evaluations: int
    total_admin_evaluations: int
    avg_innovation_score: float
    avg_admin_score: float

    @property
    def internet_ratio(self) -> float:
        if not self.total_activities:
            return 0.0
        return self.internet_enabled_activities / self.total_activities

    def to_feature_vector(self) -> list[float]:
        return [
            float(self.total_activities),
            float(self.total_recommendations),
            float(self.high_recommendations),
            float(self.critical_recommendations),
            float(self.media_total),
            float(self.total_participants),
            float(self.total_trained_teachers),
            float(self.avg_innovation_score),
            float(self.avg_admin_score),
            float(self.internet_ratio),
        ]


def _safe_score(value, default=50.0):
    return float(value) if value is not None else default


def _build_school_feature_rows(school_queryset):
    annotated_schools = (
        school_queryset.select_related('province', 'ceb')
        .annotate(
            total_activities=Count('activities', distinct=True),
            total_recommendations=Count('recommendations', distinct=True),
            high_recommendations=Count(
                'recommendations',
                filter=Q(
                    recommendations__priority__in=['HIGH', 'CRITICAL'],
                ),
                distinct=True,
            ),
            critical_recommendations=Count(
                'recommendations',
                filter=Q(recommendations__priority='CRITICAL'),
                distinct=True,
            ),
            media_total=Count('activities__media_items', distinct=True),
            total_participants=Sum('activities__participating_students'),
            total_trained_teachers=Sum('activities__trained_teachers'),
            internet_enabled_activities=Count(
                'activities',
                filter=Q(activities__has_internet=True),
                distinct=True,
            ),
            total_innovation_evaluations=Count('evaluations', distinct=True),
            total_admin_evaluations=Count('administrative_evaluations', distinct=True),
            avg_innovation_score=Avg('evaluations__performance_score'),
            avg_admin_score=Avg('administrative_evaluations__performance_score'),
        )
        .order_by('name')
    )

    rows = []
    for school in annotated_schools:
        rows.append(
            SchoolFeatureRow(
                school=school,
                school_name=school.name,
                province_name=school.province.name,
                ceb_name=school.ceb.name,
                total_activities=school.total_activities or 0,
                total_recommendations=school.total_recommendations or 0,
                high_recommendations=school.high_recommendations or 0,
                critical_recommendations=school.critical_recommendations or 0,
                media_total=school.media_total or 0,
                total_participants=school.total_participants or 0,
                total_trained_teachers=school.total_trained_teachers or 0,
                internet_enabled_activities=school.internet_enabled_activities or 0,
                total_innovation_evaluations=school.total_innovation_evaluations or 0,
                total_admin_evaluations=school.total_admin_evaluations or 0,
                avg_innovation_score=_safe_score(school.avg_innovation_score),
                avg_admin_score=_safe_score(school.avg_admin_score),
            )
        )
    return rows


def _compute_risk_score(row: SchoolFeatureRow) -> float:
    score_reference = (row.avg_innovation_score + row.avg_admin_score) / 2
    score_penalty = max(0.0, 100.0 - score_reference) * 0.55
    activity_penalty = 28.0 if row.total_activities == 0 else 12.0 if row.total_activities < 2 else 0.0
    recommendation_penalty = min(
        32.0,
        row.critical_recommendations * 14.0 + max(0, row.high_recommendations - row.critical_recommendations) * 7.0,
    )
    evidence_penalty = 6.0 if row.media_total == 0 else 0.0
    connectivity_bonus = row.internet_ratio * 5.0
    activity_bonus = min(8.0, row.total_activities * 2.0)

    risk_score = score_penalty + activity_penalty + recommendation_penalty + evidence_penalty
    risk_score -= connectivity_bonus + activity_bonus
    return round(min(100.0, max(0.0, risk_score)), 1)


def _compute_confidence_score(row: SchoolFeatureRow) -> float:
    confidence = 35.0
    confidence += min(18.0, row.total_activities * 4.5)
    confidence += min(15.0, row.total_innovation_evaluations * 7.5)
    confidence += min(15.0, row.total_admin_evaluations * 7.5)
    confidence += min(8.0, row.media_total * 4.0)
    confidence += min(5.0, row.total_recommendations * 2.5)
    confidence += 4.0 if row.total_participants > 0 else 0.0
    confidence += 3.0 if row.total_trained_teachers > 0 else 0.0
    return round(min(98.0, confidence), 1)


def _profile_from_risk_score(risk_score: float):
    if risk_score >= 65:
        return 'Risque eleve', 'danger'
    if risk_score >= 40:
        return 'Suivi renforce', 'warning'
    return 'Bonne dynamique', 'success'


def _build_explanation(row: SchoolFeatureRow, profile_label: str) -> str:
    reasons = []
    if row.total_activities == 0:
        reasons.append("aucune activite remontee")
    elif row.total_activities < 2:
        reasons.append("volume d'activites encore faible")
    if row.avg_innovation_score < 60:
        reasons.append("resultats d'innovation a renforcer")
    if row.avg_admin_score < 60:
        reasons.append("pilotage administratif a consolider")
    if row.critical_recommendations:
        reasons.append("recommandations critiques en attente")
    elif row.high_recommendations:
        reasons.append("recommandations prioritaires a traiter")
    if row.media_total == 0:
        reasons.append("peu de preuves terrain televersees")

    if not reasons:
        if profile_label == 'Bonne dynamique':
            reasons.append("performances stables et activites regulieres")
        else:
            reasons.append("situation intermediaire necessitant un suivi")

    return ', '.join(reasons[:3])


def _build_action(row: SchoolFeatureRow, profile_label: str) -> str:
    if profile_label == 'Risque eleve':
        return (
            "Prevoir un accompagnement prioritaire, renforcer le suivi pedagogique "
            "et traiter immediatement les contraintes critiques."
        )
    if profile_label == 'Suivi renforce':
        return (
            "Maintenir un suivi rapproche, augmenter les activites documentees "
            "et consolider les evaluations."
        )
    return (
        "Capitaliser les bonnes pratiques de cette ecole et les partager avec les "
        "autres unites du perimetre."
    )


def _standardize_matrix(feature_matrix):
    if SKLEARN_AVAILABLE:
        scaler = StandardScaler()
        return scaler.fit_transform(feature_matrix)

    means = feature_matrix.mean(axis=0)
    stds = feature_matrix.std(axis=0)
    stds[stds == 0] = 1.0
    return (feature_matrix - means) / stds


def _run_kmeans_numpy(feature_matrix, cluster_count):
    normalized = _standardize_matrix(feature_matrix)
    row_scores = normalized.sum(axis=1)
    sorted_indices = np.argsort(row_scores)
    seed_positions = np.linspace(0, len(sorted_indices) - 1, cluster_count).astype(int)
    centroids = normalized[sorted_indices[seed_positions]].copy()

    labels = np.zeros(len(normalized), dtype=int)
    for _ in range(20):
        distances = np.linalg.norm(normalized[:, None, :] - centroids[None, :, :], axis=2)
        new_labels = distances.argmin(axis=1)
        if np.array_equal(new_labels, labels):
            break
        labels = new_labels
        for cluster_index in range(cluster_count):
            cluster_points = normalized[labels == cluster_index]
            if len(cluster_points):
                centroids[cluster_index] = cluster_points.mean(axis=0)

    return labels


def _cluster_profiles(feature_matrix, risk_scores):
    sample_size = len(feature_matrix)
    if sample_size < 3:
        return None, 'Analyse individuelle locale'

    cluster_count = min(3, sample_size)
    if SKLEARN_AVAILABLE:
        normalized = _standardize_matrix(feature_matrix)
        model = KMeans(n_clusters=cluster_count, random_state=42, n_init=10)
        labels = model.fit_predict(normalized)
        engine_name = 'K-Means scikit-learn'
    else:
        labels = _run_kmeans_numpy(feature_matrix, cluster_count)
        engine_name = 'K-Means local (numpy)'

    cluster_risk = {}
    for cluster_index in range(cluster_count):
        cluster_values = risk_scores[labels == cluster_index]
        cluster_risk[cluster_index] = float(cluster_values.mean()) if len(cluster_values) else 0.0

    sorted_clusters = [
        cluster_index
        for cluster_index, _ in sorted(cluster_risk.items(), key=lambda item: item[1], reverse=True)
    ]
    profile_labels = ['Risque eleve', 'Suivi renforce', 'Bonne dynamique']

    cluster_profiles = {}
    for order_index, cluster_index in enumerate(sorted_clusters):
        label_index = min(order_index, len(profile_labels) - 1)
        cluster_profiles[cluster_index] = profile_labels[label_index]

    return [cluster_profiles[label] for label in labels], engine_name


def build_school_ai_analysis(school_queryset, limit=8):
    rows = _build_school_feature_rows(school_queryset)
    if not rows:
        return {
            'enabled': False,
            'engine_name': 'Aucune analyse disponible',
            'insights': [],
            'summary': {
                'high_risk': 0,
                'monitored': 0,
                'healthy': 0,
                'total_schools': 0,
                'avg_confidence': 0,
            },
            'chart_labels': '[]',
            'chart_values': '[]',
            'confidence_chart_values': '[]',
            'methodology': {
                'engine_mode': 'Aucun',
                'description': "Aucune donnee exploitable n'est encore disponible pour lancer le modele.",
                'target': '',
                'confidence_rule': '',
                'features': [],
            },
        }

    feature_matrix = np.array([row.to_feature_vector() for row in rows], dtype=float)
    risk_scores = np.array([_compute_risk_score(row) for row in rows], dtype=float)
    confidence_scores = np.array([_compute_confidence_score(row) for row in rows], dtype=float)
    clustered_profiles, engine_name = _cluster_profiles(feature_matrix, risk_scores)

    insights = []
    for index, row in enumerate(rows):
        risk_score = float(risk_scores[index])
        confidence_score = float(confidence_scores[index])
        if clustered_profiles:
            profile_label = clustered_profiles[index]
            badge = 'danger' if profile_label == 'Risque eleve' else 'warning' if profile_label == 'Suivi renforce' else 'success'
        else:
            profile_label, badge = _profile_from_risk_score(risk_score)

        insights.append(
            {
                'school': row.school,
                'school_name': row.school_name,
                'province_name': row.province_name,
                'ceb_name': row.ceb_name,
                'risk_score': risk_score,
                'confidence_score': confidence_score,
                'profile_label': profile_label,
                'badge': badge,
                'explanation': _build_explanation(row, profile_label),
                'recommended_action': _build_action(row, profile_label),
                'total_activities': row.total_activities,
                'avg_innovation_score': round(row.avg_innovation_score, 1),
                'avg_admin_score': round(row.avg_admin_score, 1),
                'critical_recommendations': row.critical_recommendations,
                'high_recommendations': row.high_recommendations,
            }
        )

    insights.sort(key=lambda item: (-item['risk_score'], item['school_name']))
    visible_insights = insights[:limit]

    return {
        'enabled': True,
        'engine_name': engine_name,
        'insights': visible_insights,
        'summary': {
            'high_risk': sum(1 for item in insights if item['profile_label'] == 'Risque eleve'),
            'monitored': sum(1 for item in insights if item['profile_label'] == 'Suivi renforce'),
            'healthy': sum(1 for item in insights if item['profile_label'] == 'Bonne dynamique'),
            'total_schools': len(insights),
            'avg_confidence': round(float(confidence_scores.mean()), 1),
        },
        'chart_labels': json.dumps([item['school_name'] for item in visible_insights]),
        'chart_values': json.dumps([item['risk_score'] for item in visible_insights]),
        'confidence_chart_values': json.dumps([item['confidence_score'] for item in visible_insights]),
        'methodology': {
            'engine_mode': engine_name,
            'description': (
                "Le module IA regroupe les ecoles selon un clustering de type K-Means "
                "sur les activites, evaluations, recommandations et preuves terrain."
            ),
            'target': (
                "Identifier automatiquement les ecoles a risque eleve, les ecoles a "
                "suivi renforce et les ecoles en bonne dynamique."
            ),
            'confidence_rule': (
                "Le score de confiance augmente avec le volume d'activites, la presence "
                "d'evaluations, les recommandations documentees et les preuves terrain."
            ),
            'features': [
                "nombre d'activites",
                "recommandations critiques et prioritaires",
                "score moyen d'innovation",
                "score administratif moyen",
                "volume de participants",
                "preuves terrain televersees",
                "activites avec acces Internet",
            ],
        },
    }
