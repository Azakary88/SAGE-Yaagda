from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Region(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Province(models.Model):
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='provinces')
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=120)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['region', 'code'], name='unique_province_code_per_region'),
            models.UniqueConstraint(fields=['region', 'name'], name='unique_province_name_per_region'),
        ]

    def __str__(self):
        return self.name


class CEB(models.Model):
    province = models.ForeignKey(Province, on_delete=models.CASCADE, related_name='cebs')
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=120)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['province', 'code'], name='unique_ceb_code_per_province'),
            models.UniqueConstraint(fields=['province', 'name'], name='unique_ceb_name_per_province'),
        ]

    def __str__(self):
        return self.name


class School(models.Model):
    class SchoolType(models.TextChoices):
        PUBLIC = 'PUBLIC', 'Publique'
        PRIVATE = 'PRIVATE', 'Privée'
        COMMUNITY = 'COMMUNITY', 'Communautaire'

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        INACTIVE = 'INACTIVE', 'Inactive'

    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=255)
    province = models.ForeignKey(Province, on_delete=models.PROTECT, related_name='schools')
    ceb = models.ForeignKey(CEB, on_delete=models.PROTECT, related_name='schools')
    school_type = models.CharField(max_length=20, choices=SchoolType.choices, default=SchoolType.PUBLIC)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    locality = models.CharField(max_length=120, blank=True)
    student_capacity = models.PositiveIntegerField(default=0)
    director = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_schools',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['ceb', 'name'], name='unique_school_name_per_ceb'),
        ]

    def __str__(self):
        return f'{self.name} ({self.code})'


class BaseAdministrativeEvaluation(models.Model):
    evaluator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_created',
    )
    evaluation_date = models.DateField(default=timezone.now)
    planning_score = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    execution_score = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    reporting_score = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    strengths = models.TextField(blank=True)
    constraints = models.TextField(blank=True)
    recommendations = models.TextField(blank=True)
    performance_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-evaluation_date', '-id']

    def compute_performance_score(self):
        average = (self.planning_score + self.execution_score + self.reporting_score) / 3
        return Decimal(str(round(average * 20, 2)))

    def save(self, *args, **kwargs):
        self.performance_score = self.compute_performance_score()
        super().save(*args, **kwargs)


class ProvinceEvaluation(BaseAdministrativeEvaluation):
    province = models.ForeignKey(
        Province,
        on_delete=models.CASCADE,
        related_name='administrative_evaluations',
    )

    class Meta(BaseAdministrativeEvaluation.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=['province', 'evaluation_date'],
                name='unique_province_evaluation_per_day',
            ),
        ]

    def __str__(self):
        return f'Évaluation province {self.province.name} ({self.evaluation_date})'


class CEBEvaluation(BaseAdministrativeEvaluation):
    ceb = models.ForeignKey(
        CEB,
        on_delete=models.CASCADE,
        related_name='administrative_evaluations',
    )

    class Meta(BaseAdministrativeEvaluation.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=['ceb', 'evaluation_date'],
                name='unique_ceb_evaluation_per_day',
            ),
        ]

    def __str__(self):
        return f'Évaluation CEB {self.ceb.name} ({self.evaluation_date})'


class SchoolAdministrativeEvaluation(BaseAdministrativeEvaluation):
    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name='administrative_evaluations',
    )

    class Meta(BaseAdministrativeEvaluation.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=['school', 'evaluation_date'],
                name='unique_school_admin_evaluation_per_day',
            ),
        ]

    def __str__(self):
        return f'Évaluation école {self.school.name} ({self.evaluation_date})'
