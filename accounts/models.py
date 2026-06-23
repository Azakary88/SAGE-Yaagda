from django.contrib.auth.models import AbstractUser
from django.db import models

from schools.models import CEB, Province, Region


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMINISTRATOR = 'ADMINISTRATOR', 'Administrateur'
        REGIONAL_AGENT = 'REGIONAL_AGENT', 'Agent régional'
        PROVINCIAL_USER = 'PROVINCIAL_USER', 'Utilisateur provincial'
        PEDAGOGICAL_SUPERVISOR = 'PEDAGOGICAL_SUPERVISOR', 'Encadreur pédagogique'
        SCHOOL_DIRECTOR = 'SCHOOL_DIRECTOR', "Directeur d'école"

    role = models.CharField(
        max_length=32,
        choices=Role.choices,
        default=Role.REGIONAL_AGENT,
    )
    phone_number = models.CharField(max_length=20, blank=True)
    job_title = models.CharField(max_length=120, blank=True)
    region = models.ForeignKey(
        Region,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
    )
    province = models.ForeignKey(
        Province,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
    )
    ceb = models.ForeignKey(
        CEB,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
    )

    def has_role(self, *roles):
        return self.is_superuser or self.role in roles

    @property
    def can_add_activity(self):
        return self.has_role(self.Role.ADMINISTRATOR, self.Role.SCHOOL_DIRECTOR)

    @property
    def can_add_school(self):
        return self.has_role(self.Role.PEDAGOGICAL_SUPERVISOR, self.Role.ADMINISTRATOR)

    @property
    def can_add_province(self):
        return self.has_role(self.Role.REGIONAL_AGENT, self.Role.ADMINISTRATOR)

    @property
    def can_add_ceb(self):
        return self.has_role(self.Role.PROVINCIAL_USER, self.Role.ADMINISTRATOR)

    @property
    def can_add_provincial_user(self):
        return self.has_role(self.Role.REGIONAL_AGENT, self.Role.ADMINISTRATOR)

    @property
    def can_add_pedagogical_supervisor(self):
        return self.has_role(self.Role.PROVINCIAL_USER, self.Role.ADMINISTRATOR)

    @property
    def can_add_school_director(self):
        return self.has_role(self.Role.PEDAGOGICAL_SUPERVISOR, self.Role.ADMINISTRATOR)

    @property
    def can_access_admin(self):
        return self.is_superuser or self.is_staff

    def can_manage_activity(self, activity):
        return self.is_superuser or (
            self.role == self.Role.ADMINISTRATOR
            or (
                self.role == self.Role.SCHOOL_DIRECTOR
                and activity.school.director_id == self.id
            )
        )

    def can_manage_school(self, school):
        return self.is_superuser or (
            self.role == self.Role.ADMINISTRATOR
            or (
            self.role == self.Role.PEDAGOGICAL_SUPERVISOR
            and self.ceb_id is not None
            and school.ceb_id == self.ceb_id
            )
        )

    def can_manage_province(self, province):
        return self.is_superuser or (
            self.role == self.Role.ADMINISTRATOR
            or (
                self.role == self.Role.REGIONAL_AGENT
                and self.region_id is not None
                and province.region_id == self.region_id
            )
        )

    def can_manage_ceb(self, ceb):
        return self.is_superuser or (
            self.role == self.Role.ADMINISTRATOR
            or (
                self.role == self.Role.PROVINCIAL_USER
                and self.province_id is not None
                and ceb.province_id == self.province_id
            )
        )

    def can_manage_provincial_user(self, user):
        return self.is_superuser or (
            self.role == self.Role.ADMINISTRATOR
            or (
                self.role == self.Role.REGIONAL_AGENT
                and user.role == self.Role.PROVINCIAL_USER
                and self.region_id is not None
                and user.province_id is not None
                and user.province.region_id == self.region_id
            )
        )

    def can_manage_pedagogical_supervisor(self, user):
        return self.is_superuser or (
            self.role == self.Role.ADMINISTRATOR
            or (
                self.role == self.Role.PROVINCIAL_USER
                and user.role == self.Role.PEDAGOGICAL_SUPERVISOR
                and self.province_id is not None
                and user.ceb_id is not None
                and user.ceb.province_id == self.province_id
            )
        )

    def can_manage_school_director(self, user):
        return self.is_superuser or (
            self.role == self.Role.ADMINISTRATOR
            or (
                self.role == self.Role.PEDAGOGICAL_SUPERVISOR
                and user.role == self.Role.SCHOOL_DIRECTOR
                and self.ceb_id is not None
                and user.ceb_id == self.ceb_id
            )
        )

    def __str__(self):
        full_name = self.get_full_name().strip()
        label = full_name or self.username
        return f'{label} - {self.get_role_display()}'
