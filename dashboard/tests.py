from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from innovations.models import Activity, ActivityMedia, Evaluation, Innovation
from schools.models import CEB, CEBEvaluation, Province, ProvinceEvaluation, Region, School, SchoolAdministrativeEvaluation

from .ai import build_school_ai_analysis


class DashboardScopeTests(TestCase):
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
        )
        self.other_director = User.objects.create_user(
            username='directeur2',
            password='test-pass-123',
            role=User.Role.SCHOOL_DIRECTOR,
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
        self.innovation = Innovation.objects.get(slug='tic')
        self.activity = Activity.objects.create(
            school=self.school,
            innovation=self.innovation,
            title='Activite de reference',
            created_by=self.director,
        )
        self.other_activity = Activity.objects.create(
            school=self.other_school,
            innovation=self.innovation,
            title='Activite externe',
            created_by=self.other_director,
        )
        self.regional_agent = User.objects.create_user(
            username='regional',
            password='test-pass-123',
            role=User.Role.REGIONAL_AGENT,
            region=self.region,
        )
        self.provincial_user = User.objects.create_user(
            username='provincial',
            password='test-pass-123',
            role=User.Role.PROVINCIAL_USER,
            region=self.region,
            province=self.province,
        )
        self.supervisor = User.objects.create_user(
            username='supervisor',
            password='test-pass-123',
            role=User.Role.PEDAGOGICAL_SUPERVISOR,
            region=self.region,
            province=self.province,
            ceb=self.ceb,
        )
        ProvinceEvaluation.objects.create(
            province=self.province,
            evaluator=self.regional_agent,
            evaluation_date='2026-04-24',
            planning_score=4,
            execution_score=4,
            reporting_score=4,
        )
        CEBEvaluation.objects.create(
            ceb=self.ceb,
            evaluator=self.provincial_user,
            evaluation_date='2026-04-24',
            planning_score=4,
            execution_score=3,
            reporting_score=4,
        )
        SchoolAdministrativeEvaluation.objects.create(
            school=self.school,
            evaluator=self.supervisor,
            evaluation_date='2026-04-24',
            planning_score=5,
            execution_score=4,
            reporting_score=4,
        )
        ActivityMedia.objects.create(
            activity=self.activity,
            file=SimpleUploadedFile('photo.jpg', b'fake-image', content_type='image/jpeg'),
            comment='Photo d activite',
            uploaded_by=self.director,
        )

    def test_regional_dashboard_only_lists_region_provinces(self):
        self.client.login(username='regional', password='test-pass-123')

        response = self.client.get(reverse('dashboard:home'))

        self.assertEqual(response.context['dashboard_level'], 'province')
        self.assertEqual([province.id for province in response.context['province_rows']], [self.province.id])
        self.assertTrue(response.context['ai_analysis']['enabled'])

    def test_provincial_dashboard_only_lists_province_cebs(self):
        self.client.login(username='provincial', password='test-pass-123')

        response = self.client.get(reverse('dashboard:home'))

        self.assertEqual(response.context['dashboard_level'], 'ceb')
        self.assertEqual([ceb.id for ceb in response.context['ceb_rows']], [self.ceb.id])
        self.assertEqual(response.context['ai_analysis']['summary']['total_schools'], 1)

    def test_supervisor_dashboard_only_lists_ceb_schools(self):
        self.client.login(username='supervisor', password='test-pass-123')

        response = self.client.get(reverse('dashboard:home'))

        self.assertEqual(response.context['dashboard_level'], 'school')
        self.assertEqual([school.id for school in response.context['school_rows']], [self.school.id])

    def test_director_dashboard_only_lists_own_activities_and_media(self):
        Activity.objects.create(
            school=self.school,
            innovation=self.innovation,
            title='Deuxieme activite memes eleves',
            participating_students=12,
            created_by=self.director,
        )
        self.client.login(username='directeur', password='test-pass-123')

        response = self.client.get(reverse('dashboard:home'))

        self.assertEqual(response.context['dashboard_level'], 'director')
        self.assertEqual(
            [activity.title for activity in response.context['director_activities']],
            ['Deuxieme activite memes eleves', self.activity.title],
        )
        self.assertEqual(response.context['secondary_metric_value'], 1)
        self.assertEqual(response.context['tertiary_metric_value'], 12)
        self.assertEqual(response.context['ai_analysis']['insights'][0]['school_name'], self.school.name)

    def test_ai_analysis_page_is_available_in_user_scope(self):
        self.client.login(username='regional', password='test-pass-123')

        response = self.client.get(reverse('dashboard:ai_analysis'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Analyse IA')
        self.assertEqual(response.context['ai_analysis']['summary']['total_schools'], 1)

    def test_ai_analysis_pdf_export_returns_pdf(self):
        self.client.login(username='regional', password='test-pass-123')

        response = self.client.get(reverse('dashboard:ai_analysis_pdf'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('analyse-ia-dreppnf.pdf', response['Content-Disposition'])


class DashboardAIModuleTests(TestCase):
    def setUp(self):
        self.region = Region.objects.create(code='REG', name='Region IA')
        self.province = Province.objects.create(region=self.region, code='P1', name='Province IA')
        self.ceb = CEB.objects.create(province=self.province, code='CEB1', name='CEB IA')
        self.innovation = Innovation.objects.get(slug='tic')
        self.evaluator = User.objects.create_user(username='eva', password='test-pass-123')

        self.school_a = School.objects.create(code='S1', name='Ecole A', province=self.province, ceb=self.ceb)
        self.school_b = School.objects.create(code='S2', name='Ecole B', province=self.province, ceb=self.ceb)
        self.school_c = School.objects.create(code='S3', name='Ecole C', province=self.province, ceb=self.ceb)

        activity_a = Activity.objects.create(
            school=self.school_a,
            innovation=self.innovation,
            title='Activite A',
            participating_students=35,
            trained_teachers=4,
            has_internet=True,
        )
        Activity.objects.create(
            school=self.school_b,
            innovation=self.innovation,
            title='Activite B',
            participating_students=10,
            trained_teachers=1,
            has_internet=False,
        )

        Evaluation.objects.create(
            school=self.school_a,
            innovation=self.innovation,
            activity=activity_a,
            evaluator=self.evaluator,
            implementation_level=5,
            student_participation=5,
        )
        Evaluation.objects.create(
            school=self.school_b,
            innovation=self.innovation,
            evaluator=self.evaluator,
            implementation_level=2,
            student_participation=2,
        )
        SchoolAdministrativeEvaluation.objects.create(
            school=self.school_a,
            evaluator=self.evaluator,
            evaluation_date='2026-04-24',
            planning_score=5,
            execution_score=4,
            reporting_score=5,
        )
        SchoolAdministrativeEvaluation.objects.create(
            school=self.school_b,
            evaluator=self.evaluator,
            evaluation_date='2026-04-24',
            planning_score=2,
            execution_score=2,
            reporting_score=2,
        )

    def test_ai_module_returns_ranked_school_profiles(self):
        analysis = build_school_ai_analysis(School.objects.filter(province=self.province), limit=10)

        self.assertTrue(analysis['enabled'])
        self.assertEqual(analysis['summary']['total_schools'], 3)
        self.assertEqual(len(analysis['insights']), 3)
        self.assertIn('K-Means', analysis['engine_name'])
        self.assertGreaterEqual(analysis['insights'][0]['risk_score'], analysis['insights'][-1]['risk_score'])
        self.assertIn('avg_confidence', analysis['summary'])
        self.assertIn('methodology', analysis)
        self.assertIn('confidence_score', analysis['insights'][0])

    def test_ai_module_marks_missing_scores_as_not_available(self):
        analysis = build_school_ai_analysis(School.objects.filter(province=self.province), limit=10)

        school_c_insight = next(
            insight for insight in analysis['insights'] if insight['school'].id == self.school_c.id
        )

        self.assertEqual(school_c_insight['avg_innovation_score'], 'N/D')
        self.assertEqual(school_c_insight['avg_admin_score'], 'N/D')
        self.assertIn("aucune évaluation", school_c_insight['explanation'])
