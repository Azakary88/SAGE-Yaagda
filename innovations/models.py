from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from schools.models import Province, School


class Innovation(models.Model):
    class Category(models.TextChoices):
        TRADES = 'TRADES', 'Metiers scolaires'
        ICT = 'ICT', 'TIC'
        ENGLISH = 'ENGLISH', 'Anglais'

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(unique=True)
    category = models.CharField(max_length=20, choices=Category.choices)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Activity(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='activities')
    innovation = models.ForeignKey(Innovation, on_delete=models.PROTECT, related_name='activities')
    title = models.CharField(max_length=180)
    reporting_date = models.DateField(default=timezone.now)
    classes_concerned = models.CharField(max_length=180, blank=True)
    description = models.TextField(blank=True)
    participating_students = models.PositiveIntegerField(default=0)
    trained_teachers = models.PositiveIntegerField(default=0)
    taught_hours = models.PositiveIntegerField(default=0)
    computers_count = models.PositiveIntegerField(default=0)
    has_internet = models.BooleanField(default=False)
    quantity_produced = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    available_resources = models.TextField(blank=True)
    challenges = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activities',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-reporting_date', '-created_at']

    def __str__(self):
        return f'{self.school.name} - {self.innovation.name}'


class ActivityMedia(models.Model):
    activity = models.ForeignKey(
        Activity,
        on_delete=models.CASCADE,
        related_name='media_items',
    )
    file = models.FileField(upload_to='activities/%Y/%m/%d/')
    comment = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_activity_media',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Media {self.activity.title} ({self.created_at:%Y-%m-%d})'


class Evaluation(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='evaluations')
    innovation = models.ForeignKey(Innovation, on_delete=models.PROTECT, related_name='evaluations')
    activity = models.ForeignKey(
        Activity,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='evaluations',
    )
    evaluator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='evaluations',
    )
    evaluation_date = models.DateField(default=timezone.now)
    implementation_level = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    student_participation = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    observed_results = models.TextField(blank=True)
    constraints = models.TextField(blank=True)
    performance_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        ordering = ['-evaluation_date', '-id']

    def save(self, *args, **kwargs):
        raw_score = (self.implementation_level * 0.6 + self.student_participation * 0.4) * 20
        self.performance_score = Decimal(str(round(raw_score, 2)))
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Evaluation {self.school.name} - {self.innovation.name}'


class Recommendation(models.Model):
    class Priority(models.TextChoices):
        LOW = 'LOW', 'Faible'
        MEDIUM = 'MEDIUM', 'Moyenne'
        HIGH = 'HIGH', 'Elevee'
        CRITICAL = 'CRITICAL', 'Critique'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'En attente'
        IMPLEMENTED = 'IMPLEMENTED', 'Mise en oeuvre'
        ARCHIVED = 'ARCHIVED', 'Archivee'

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='recommendations')
    innovation = models.ForeignKey(
        Innovation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recommendations',
    )
    based_on_evaluation = models.OneToOneField(
        Evaluation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='system_recommendation',
    )
    recommendation_text = models.TextField()
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    generated_by_system = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Recommandation {self.school.name} - {self.get_priority_display()}'


class Report(models.Model):
    class Scope(models.TextChoices):
        SCHOOL = 'SCHOOL', 'Par ecole'
        PROVINCE = 'PROVINCE', 'Par province'
        REGIONAL = 'REGIONAL', 'Regional'

    title = models.CharField(max_length=180)
    scope = models.CharField(max_length=20, choices=Scope.choices)
    school = models.ForeignKey(
        School,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports',
    )
    province = models.ForeignKey(
        Province,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports',
    )
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_reports',
    )
    file_path = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
