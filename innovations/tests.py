from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from schools.models import CEB, Province, Region, School

from .forms import ActivityMediaForm
from .models import Activity, ActivityMedia, Evaluation, Innovation


VALID_GIF_BYTES = (
    b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!'
    b'\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00'
    b'\x00\x02\x02D\x01\x00;'
)


class EvaluationTests(TestCase):
    def test_performance_score_is_computed_automatically(self):
        region = Region.objects.create(code='YAAG', name='Yaagda')
        province = Province.objects.create(region=region, code='P1', name='Province 1')
        ceb = CEB.objects.create(province=province, code='CEB1', name='CEB 1')
        school = School.objects.create(code='E001', name='Ecole Test', province=province, ceb=ceb)
        innovation = Innovation.objects.get(slug='tic')
        evaluator = User.objects.create_user(username='encadreur', password='test-pass-123')

        evaluation = Evaluation.objects.create(
            school=school,
            innovation=innovation,
            evaluator=evaluator,
            implementation_level=4,
            student_participation=3,
        )

        self.assertEqual(float(evaluation.performance_score), 72.0)


class ActivityPermissionTests(TestCase):
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
            username='agent',
            password='test-pass-123',
            role=User.Role.REGIONAL_AGENT,
            region=self.region,
        )

    def _sample_image(self, name='photo.jpg'):
        return SimpleUploadedFile(name, VALID_GIF_BYTES, content_type='image/gif')

    def test_school_director_can_create_activity_for_managed_school(self):
        self.client.login(username='directeur', password='test-pass-123')

        response = self.client.post(
            reverse('innovations:activity_create'),
            data={
                'school': self.school.id,
                'innovation': self.innovation.id,
                'title': 'Initiation numerique',
                'reporting_date': '2026-04-22',
                'classes_concerned': 'CM1',
                'description': 'Atelier TIC',
                'participating_students': 24,
                'trained_teachers': 2,
                'taught_hours': 4,
                'computers_count': 10,
                'has_internet': True,
                'quantity_produced': '0.00',
                'available_resources': 'Salle informatique',
                'challenges': 'RAS',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Activity.objects.filter(title='Initiation numerique').exists())

    def test_regional_agent_cannot_create_activity(self):
        self.client.login(username='agent', password='test-pass-123')

        response = self.client.get(reverse('innovations:activity_create'))

        self.assertEqual(response.status_code, 403)

    def test_school_director_sees_only_his_school_activities(self):
        self.client.login(username='directeur', password='test-pass-123')

        response = self.client.get(reverse('innovations:activity_list'))

        activities = list(response.context['activities'])
        self.assertEqual([activity.id for activity in activities], [self.activity.id])

    def test_school_director_can_update_and_delete_own_activity(self):
        self.client.login(username='directeur', password='test-pass-123')

        update_response = self.client.post(
            reverse('innovations:activity_update', args=[self.activity.id]),
            data={
                'school': self.school.id,
                'innovation': self.innovation.id,
                'title': 'Activite modifiee',
                'reporting_date': '2026-04-22',
                'classes_concerned': 'CM1',
                'description': 'Mise a jour',
                'participating_students': 18,
                'trained_teachers': 1,
                'taught_hours': 3,
                'computers_count': 8,
                'has_internet': True,
                'quantity_produced': '0.00',
                'available_resources': 'Salle',
                'challenges': 'RAS',
            },
        )
        self.activity.refresh_from_db()

        delete_response = self.client.post(reverse('innovations:activity_delete', args=[self.activity.id]))

        self.assertEqual(update_response.status_code, 302)
        self.assertEqual(self.activity.title, 'Activite modifiee')
        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(Activity.objects.filter(id=self.activity.id).exists())

    def test_school_director_cannot_modify_activity_of_another_school(self):
        self.client.login(username='directeur', password='test-pass-123')

        response = self.client.get(reverse('innovations:activity_update', args=[self.other_activity.id]))

        self.assertEqual(response.status_code, 403)

    def test_school_director_can_upload_and_delete_media_for_own_activity(self):
        self.client.login(username='directeur', password='test-pass-123')

        create_response = self.client.post(
            reverse('innovations:media_create', args=[self.activity.id]),
            data={
                'file': self._sample_image(),
                'comment': 'Photo de demonstration',
            },
        )
        media = ActivityMedia.objects.get(activity=self.activity)
        delete_response = self.client.post(reverse('innovations:media_delete', args=[media.id]))

        self.assertEqual(create_response.status_code, 302)
        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(ActivityMedia.objects.filter(id=media.id).exists())

    def test_activity_detail_shows_inline_upload_form_for_director(self):
        self.client.login(username='directeur', password='test-pass-123')

        response = self.client.get(reverse('innovations:activity_detail', args=[self.activity.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ajouter')
        self.assertContains(response, 'name="file"', html=False)
        self.assertContains(response, 'name="comment"', html=False)

    def test_school_director_can_upload_media_from_activity_detail_page(self):
        self.client.login(username='directeur', password='test-pass-123')

        response = self.client.post(
            reverse('innovations:activity_detail', args=[self.activity.id]),
            data={
                'file': self._sample_image(),
                'comment': 'Photo prise pendant l activite',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ActivityMedia.objects.filter(
                activity=self.activity,
                comment='Photo prise pendant l activite',
            ).exists()
        )

    def test_oversized_media_upload_is_rejected(self):
        self.client.login(username='directeur', password='test-pass-123')
        oversized_image = SimpleUploadedFile(
            'trop-grand.png',
            b'x' * (ActivityMediaForm.MAX_FILE_SIZE + 1),
            content_type='image/png',
        )

        response = self.client.post(
            reverse('innovations:activity_detail', args=[self.activity.id]),
            data={
                'file': oversized_image,
                'comment': 'Image trop lourde',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '2 Mo maximum')
        self.assertFalse(ActivityMedia.objects.filter(comment='Image trop lourde').exists())

    @patch('innovations.models.ActivityMedia.save', side_effect=Exception('storage unavailable'))
    def test_media_storage_error_is_displayed_on_detail_page(self, mocked_save):
        self.client.login(username='directeur', password='test-pass-123')

        response = self.client.post(
            reverse('innovations:activity_detail', args=[self.activity.id]),
            data={
                'file': self._sample_image(),
                'comment': 'Erreur stockage',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Le média n&#x27;a pas pu être enregistré")
        self.assertFalse(ActivityMedia.objects.filter(comment='Erreur stockage').exists())

    def test_authorized_regional_agent_can_see_uploaded_activity_media(self):
        ActivityMedia.objects.create(
            activity=self.activity,
            file=self._sample_image(),
            comment='Photo partagee',
            uploaded_by=self.director,
        )
        self.client.login(username='agent', password='test-pass-123')

        response = self.client.get(reverse('innovations:activity_detail', args=[self.activity.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Photo partagee')
        self.assertNotContains(response, 'name="file"', html=False)

    def test_school_director_cannot_upload_media_for_other_school_activity(self):
        self.client.login(username='directeur', password='test-pass-123')

        response = self.client.post(
            reverse('innovations:media_create', args=[self.other_activity.id]),
            data={
                'file': self._sample_image('other.jpg'),
                'comment': 'Tentative externe',
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(ActivityMedia.objects.filter(activity=self.other_activity).exists())


class ActivityReportTests(TestCase):
    def _sample_image(self, name='report.gif'):
        return SimpleUploadedFile(name, VALID_GIF_BYTES, content_type='image/gif')

    def setUp(self):
        self.region = Region.objects.create(code='YAAG', name='Yaagda')
        self.other_region = Region.objects.create(code='EST', name='Est')

        self.province_a = Province.objects.create(region=self.region, code='P1', name='Province A')
        self.province_b = Province.objects.create(region=self.region, code='P2', name='Province B')
        self.other_province = Province.objects.create(region=self.other_region, code='P3', name='Province Externe')

        self.ceb_a1 = CEB.objects.create(province=self.province_a, code='CEB1', name='CEB A1')
        self.ceb_a2 = CEB.objects.create(province=self.province_a, code='CEB2', name='CEB A2')
        self.ceb_b1 = CEB.objects.create(province=self.province_b, code='CEB3', name='CEB B1')
        self.other_ceb = CEB.objects.create(province=self.other_province, code='CEB4', name='CEB Externe')

        self.director_a1 = User.objects.create_user(
            username='directeur-a1',
            password='test-pass-123',
            role=User.Role.SCHOOL_DIRECTOR,
        )
        self.director_a2 = User.objects.create_user(
            username='directeur-a2',
            password='test-pass-123',
            role=User.Role.SCHOOL_DIRECTOR,
        )
        self.director_b1 = User.objects.create_user(
            username='directeur-b1',
            password='test-pass-123',
            role=User.Role.SCHOOL_DIRECTOR,
        )
        self.director_ext = User.objects.create_user(
            username='directeur-ext',
            password='test-pass-123',
            role=User.Role.SCHOOL_DIRECTOR,
        )
        self.supervisor_a1 = User.objects.create_user(
            username='encadreur-a1',
            password='test-pass-123',
            role=User.Role.PEDAGOGICAL_SUPERVISOR,
            region=self.region,
            province=self.province_a,
            ceb=self.ceb_a1,
        )
        self.provincial_a = User.objects.create_user(
            username='provincial-a',
            password='test-pass-123',
            role=User.Role.PROVINCIAL_USER,
            region=self.region,
            province=self.province_a,
        )
        self.regional_agent = User.objects.create_user(
            username='regional-a',
            password='test-pass-123',
            role=User.Role.REGIONAL_AGENT,
            region=self.region,
        )

        self.school_a1 = School.objects.create(
            code='EA1',
            name='Ecole A1',
            province=self.province_a,
            ceb=self.ceb_a1,
            director=self.director_a1,
        )
        self.school_a2 = School.objects.create(
            code='EA2',
            name='Ecole A2',
            province=self.province_a,
            ceb=self.ceb_a2,
            director=self.director_a2,
        )
        self.school_b1 = School.objects.create(
            code='EB1',
            name='Ecole B1',
            province=self.province_b,
            ceb=self.ceb_b1,
            director=self.director_b1,
        )
        self.school_ext = School.objects.create(
            code='EE1',
            name='Ecole Externe',
            province=self.other_province,
            ceb=self.other_ceb,
            director=self.director_ext,
        )

        self.innovation = Innovation.objects.get(slug='tic')
        self.activity_a1 = Activity.objects.create(
            school=self.school_a1,
            innovation=self.innovation,
            title='Activite A1',
            participating_students=25,
            trained_teachers=2,
            taught_hours=4,
            created_by=self.director_a1,
        )
        self.activity_a2 = Activity.objects.create(
            school=self.school_a2,
            innovation=self.innovation,
            title='Activite A2',
            participating_students=18,
            trained_teachers=1,
            taught_hours=2,
            created_by=self.director_a2,
        )
        self.activity_b1 = Activity.objects.create(
            school=self.school_b1,
            innovation=self.innovation,
            title='Activite B1',
            participating_students=31,
            trained_teachers=3,
            taught_hours=5,
            created_by=self.director_b1,
        )
        self.activity_ext = Activity.objects.create(
            school=self.school_ext,
            innovation=self.innovation,
            title='Activite Externe',
            participating_students=12,
            trained_teachers=1,
            taught_hours=1,
            created_by=self.director_ext,
        )
        self.activity_a1_media = ActivityMedia.objects.create(
            activity=self.activity_a1,
            file=self._sample_image(),
            comment='Illustration de l activite',
            uploaded_by=self.director_a1,
        )

    def test_school_director_report_form_is_limited_to_own_activity(self):
        self.client.login(username='directeur-a1', password='test-pass-123')

        response = self.client.get(reverse('innovations:activity_report'))

        queryset = response.context['form'].fields['activity'].queryset
        self.assertEqual(list(queryset.values_list('id', flat=True)), [self.activity_a1.id])

    def test_school_director_can_generate_activity_synthesis(self):
        self.client.login(username='directeur-a1', password='test-pass-123')

        response = self.client.get(
            reverse('innovations:activity_report'),
            data={'report_kind': 'ACTIVITY', 'activity': self.activity_a1.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rapport de synthèse')
        self.assertContains(response, 'Activite A1')
        self.assertContains(response, self.activity_a1_media.file.url)
        self.assertContains(response, 'Illustration de l activite')
        self.assertNotContains(response, 'Activite A2')
        self.assertNotContains(response, 'Activite Externe')

    def test_pedagogical_supervisor_general_report_is_limited_to_his_ceb(self):
        self.client.login(username='encadreur-a1', password='test-pass-123')

        response = self.client.get(
            reverse('innovations:activity_report'),
            data={'report_kind': 'GENERAL'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Comparaison des écoles de la CEB')
        self.assertContains(response, 'Activite A1')
        self.assertNotContains(response, 'Activite A2')
        self.assertNotContains(response, 'Activite B1')
        self.assertNotContains(response, 'Activite Externe')

    def test_provincial_user_general_report_is_limited_to_his_province(self):
        self.client.login(username='provincial-a', password='test-pass-123')

        response = self.client.get(
            reverse('innovations:activity_report'),
            data={'report_kind': 'GENERAL'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Comparaison des CEB de la province')
        self.assertContains(response, 'Activite A1')
        self.assertContains(response, 'Activite A2')
        self.assertNotContains(response, 'Activite B1')
        self.assertNotContains(response, 'Activite Externe')

        metric_labels = [item['label'] for item in response.context['report_preview']['metrics']]
        self.assertNotIn('Élèves touchés', metric_labels)
        self.assertIn('Innovations suivies', metric_labels)

    def test_regional_agent_general_report_is_limited_to_his_region(self):
        self.client.login(username='regional-a', password='test-pass-123')

        response = self.client.get(
            reverse('innovations:activity_report'),
            data={'report_kind': 'GENERAL'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Comparaison des provinces')
        self.assertContains(response, 'Activite A1')
        self.assertContains(response, 'Activite A2')
        self.assertContains(response, 'Activite B1')
        self.assertNotContains(response, 'Activite Externe')

    def test_report_pdf_is_available_for_director_scope(self):
        self.client.login(username='directeur-a1', password='test-pass-123')

        response = self.client.get(
            reverse('innovations:activity_report_pdf'),
            data={'report_kind': 'GENERAL'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment;', response['Content-Disposition'])

    def test_activity_report_pdf_embeds_uploaded_image(self):
        self.client.login(username='directeur-a1', password='test-pass-123')

        response = self.client.get(
            reverse('innovations:activity_report_pdf'),
            data={'report_kind': 'ACTIVITY', 'activity': self.activity_a1.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn(b'/Subtype /Image', response.content)
