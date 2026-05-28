from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .models import CEB, CEBEvaluation, Province, ProvinceEvaluation, Region, School, SchoolAdministrativeEvaluation


class SchoolModelTests(TestCase):
    def test_school_string_representation_contains_code(self):
        region = Region.objects.create(code='YAAG', name='Yaagda')
        province = Province.objects.create(region=region, code='P1', name='Province 1')
        ceb = CEB.objects.create(province=province, code='CEB1', name='CEB 1')
        director = User.objects.create_user(
            username='directeur',
            password='test-pass-123',
            role=User.Role.SCHOOL_DIRECTOR,
        )
        school = School.objects.create(
            code='E001',
            name='Ecole Test',
            province=province,
            ceb=ceb,
            director=director,
        )

        self.assertEqual(str(school), 'Ecole Test (E001)')


class SchoolPermissionViewTests(TestCase):
    def setUp(self):
        self.region = Region.objects.create(code='YAAG', name='Yaagda')
        self.other_region = Region.objects.create(code='CENT', name='Centre')
        self.province = Province.objects.create(region=self.region, code='P1', name='Province 1')
        self.other_province = Province.objects.create(region=self.other_region, code='P2', name='Province 2')
        self.ceb = CEB.objects.create(province=self.province, code='CEB1', name='CEB 1')
        self.other_ceb = CEB.objects.create(province=self.other_province, code='CEB2', name='CEB 2')
        self.director = User.objects.create_user(
            username='directeur',
            password='test-pass-123',
            role=User.Role.SCHOOL_DIRECTOR,
            region=self.region,
            province=self.province,
            ceb=self.ceb,
        )
        self.other_director = User.objects.create_user(
            username='directeur2',
            password='test-pass-123',
            role=User.Role.SCHOOL_DIRECTOR,
            region=self.other_region,
            province=self.other_province,
            ceb=self.other_ceb,
        )
        self.school = School.objects.create(
            code='E001',
            name='Ecole Test',
            province=self.province,
            ceb=self.ceb,
            director=self.director,
        )
        self.other_school = School.objects.create(
            code='E002',
            name='Ecole Exterieure',
            province=self.other_province,
            ceb=self.other_ceb,
            director=self.other_director,
        )

    def test_pedagogical_supervisor_can_create_school(self):
        User.objects.create_user(
            username='encadreur',
            password='test-pass-123',
            role=User.Role.PEDAGOGICAL_SUPERVISOR,
            region=self.region,
            province=self.province,
            ceb=self.ceb,
        )
        self.client.login(username='encadreur', password='test-pass-123')

        response = self.client.post(
            reverse('schools:create'),
            data={
                'code': 'E003',
                'name': 'Ecole Nouvelle',
                'province': self.province.id,
                'ceb': self.ceb.id,
                'school_type': School.SchoolType.PUBLIC,
                'status': School.Status.ACTIVE,
                'locality': 'Centre',
                'student_capacity': 120,
            },
        )

        self.assertEqual(response.status_code, 302)
        school = School.objects.get(code='E003')
        self.assertIsNone(school.director)

    def test_pedagogical_supervisor_can_create_school_without_director(self):
        User.objects.create_user(
            username='encadreur',
            password='test-pass-123',
            role=User.Role.PEDAGOGICAL_SUPERVISOR,
            region=self.region,
            province=self.province,
            ceb=self.ceb,
        )
        self.client.login(username='encadreur', password='test-pass-123')

        response = self.client.post(
            reverse('schools:create'),
            data={
                'code': 'E004',
                'name': 'Ecole Sans Directeur',
                'province': self.province.id,
                'ceb': self.ceb.id,
                'school_type': School.SchoolType.PUBLIC,
                'status': School.Status.ACTIVE,
                'locality': 'Quartier Nord',
                'student_capacity': 80,
            },
        )

        self.assertEqual(response.status_code, 302)
        school = School.objects.get(code='E004')
        self.assertIsNone(school.director)

    def test_school_create_form_no_longer_exposes_director_field(self):
        User.objects.create_user(
            username='encadreur',
            password='test-pass-123',
            role=User.Role.PEDAGOGICAL_SUPERVISOR,
            region=self.region,
            province=self.province,
            ceb=self.ceb,
        )
        self.client.login(username='encadreur', password='test-pass-123')

        response = self.client.get(reverse('schools:create'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Directeur d'ecole")

    def test_regional_agent_can_create_province_but_not_ceb(self):
        User.objects.create_user(
            username='agent',
            password='test-pass-123',
            role=User.Role.REGIONAL_AGENT,
            region=self.region,
        )
        self.client.login(username='agent', password='test-pass-123')

        province_response = self.client.post(
            reverse('schools:province_create'),
            data={'region': self.region.id, 'code': 'P3', 'name': 'Province 3'},
        )
        ceb_response = self.client.get(reverse('schools:ceb_create'))

        self.assertEqual(province_response.status_code, 302)
        self.assertEqual(ceb_response.status_code, 403)
        self.assertTrue(Province.objects.filter(code='P3').exists())

    def test_provincial_user_can_create_and_manage_ceb_of_his_province(self):
        User.objects.create_user(
            username='province',
            password='test-pass-123',
            role=User.Role.PROVINCIAL_USER,
            region=self.region,
            province=self.province,
        )
        self.client.login(username='province', password='test-pass-123')

        create_response = self.client.post(
            reverse('schools:ceb_create'),
            data={'province': self.province.id, 'code': 'CEB3', 'name': 'CEB 3'},
        )
        ceb = CEB.objects.get(code='CEB3')
        update_response = self.client.post(
            reverse('schools:ceb_update', args=[ceb.id]),
            data={'province': self.province.id, 'code': 'CEB3', 'name': 'CEB 3 Modifiee'},
        )
        ceb.refresh_from_db()
        delete_response = self.client.post(reverse('schools:ceb_delete', args=[ceb.id]))

        self.assertEqual(create_response.status_code, 302)
        self.assertEqual(update_response.status_code, 302)
        self.assertEqual(ceb.name, 'CEB 3 Modifiee')
        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(CEB.objects.filter(id=ceb.id).exists())

    def test_pedagogical_supervisor_sees_only_schools_of_his_ceb(self):
        User.objects.create_user(
            username='encadreur',
            password='test-pass-123',
            role=User.Role.PEDAGOGICAL_SUPERVISOR,
            region=self.region,
            province=self.province,
            ceb=self.ceb,
        )
        self.client.login(username='encadreur', password='test-pass-123')

        response = self.client.get(reverse('schools:list'))

        schools = list(response.context['schools'])
        self.assertEqual([school.id for school in schools], [self.school.id])

    def test_provincial_user_sees_only_cebs_of_his_province(self):
        User.objects.create_user(
            username='province',
            password='test-pass-123',
            role=User.Role.PROVINCIAL_USER,
            region=self.region,
            province=self.province,
        )
        self.client.login(username='province', password='test-pass-123')

        response = self.client.get(reverse('schools:ceb_list'))

        cebs = list(response.context['cebs'])
        self.assertEqual([ceb.id for ceb in cebs], [self.ceb.id])

    def test_regional_agent_sees_only_provinces_of_his_region(self):
        User.objects.create_user(
            username='agent',
            password='test-pass-123',
            role=User.Role.REGIONAL_AGENT,
            region=self.region,
        )
        self.client.login(username='agent', password='test-pass-123')

        response = self.client.get(reverse('schools:province_list'))

        provinces = list(response.context['provinces'])
        self.assertEqual([province.id for province in provinces], [self.province.id])

    def test_pedagogical_supervisor_can_update_and_delete_school_of_his_ceb(self):
        User.objects.create_user(
            username='encadreur',
            password='test-pass-123',
            role=User.Role.PEDAGOGICAL_SUPERVISOR,
            region=self.region,
            province=self.province,
            ceb=self.ceb,
        )
        self.client.login(username='encadreur', password='test-pass-123')

        update_response = self.client.post(
            reverse('schools:update', args=[self.school.id]),
            data={
                'code': self.school.code,
                'name': 'Ecole Test Modifiee',
                'province': self.province.id,
                'ceb': self.ceb.id,
                'school_type': School.SchoolType.PUBLIC,
                'status': School.Status.ACTIVE,
                'locality': 'Centre',
                'student_capacity': 200,
            },
        )
        self.school.refresh_from_db()

        delete_response = self.client.post(reverse('schools:delete', args=[self.school.id]))

        self.assertEqual(update_response.status_code, 302)
        self.assertEqual(self.school.name, 'Ecole Test Modifiee')
        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(School.objects.filter(id=self.school.id).exists())

    def test_pedagogical_supervisor_cannot_modify_school_outside_his_ceb(self):
        User.objects.create_user(
            username='encadreur',
            password='test-pass-123',
            role=User.Role.PEDAGOGICAL_SUPERVISOR,
            region=self.region,
            province=self.province,
            ceb=self.ceb,
        )
        self.client.login(username='encadreur', password='test-pass-123')

        response = self.client.get(reverse('schools:update', args=[self.other_school.id]))

        self.assertEqual(response.status_code, 403)

    def test_role_specific_users_can_create_administrative_evaluations(self):
        regional_agent = User.objects.create_user(
            username='agent',
            password='test-pass-123',
            role=User.Role.REGIONAL_AGENT,
            region=self.region,
        )
        provincial_user = User.objects.create_user(
            username='province',
            password='test-pass-123',
            role=User.Role.PROVINCIAL_USER,
            region=self.region,
            province=self.province,
        )
        supervisor = User.objects.create_user(
            username='encadreur',
            password='test-pass-123',
            role=User.Role.PEDAGOGICAL_SUPERVISOR,
            region=self.region,
            province=self.province,
            ceb=self.ceb,
        )

        self.client.login(username='agent', password='test-pass-123')
        province_response = self.client.post(
            reverse('schools:province_evaluation_create'),
            data={
                'province': self.province.id,
                'evaluation_date': '2026-04-24',
                'planning_score': 4,
                'execution_score': 4,
                'reporting_score': 5,
                'strengths': 'Bonne coordination',
                'constraints': 'RAS',
                'recommendations': 'Poursuivre',
            },
        )
        self.client.logout()

        self.client.login(username='province', password='test-pass-123')
        ceb_response = self.client.post(
            reverse('schools:ceb_evaluation_create'),
            data={
                'ceb': self.ceb.id,
                'evaluation_date': '2026-04-24',
                'planning_score': 4,
                'execution_score': 3,
                'reporting_score': 4,
                'strengths': 'Suivi present',
                'constraints': 'Logistique',
                'recommendations': 'Renforcer',
            },
        )
        self.client.logout()

        self.client.login(username='encadreur', password='test-pass-123')
        school_response = self.client.post(
            reverse('schools:school_evaluation_create'),
            data={
                'school': self.school.id,
                'evaluation_date': '2026-04-24',
                'planning_score': 5,
                'execution_score': 4,
                'reporting_score': 4,
                'strengths': 'Equipe motivee',
                'constraints': 'Materiel insuffisant',
                'recommendations': 'Doter',
            },
        )

        self.assertEqual(province_response.status_code, 302)
        self.assertEqual(ceb_response.status_code, 302)
        self.assertEqual(school_response.status_code, 302)
        self.assertTrue(ProvinceEvaluation.objects.filter(province=self.province, evaluator=regional_agent).exists())
        self.assertTrue(CEBEvaluation.objects.filter(ceb=self.ceb, evaluator=provincial_user).exists())
        self.assertTrue(SchoolAdministrativeEvaluation.objects.filter(school=self.school, evaluator=supervisor).exists())
