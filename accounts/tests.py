from django.test import Client, TestCase
from django.urls import reverse

from innovations.forms import ActivityForm
from schools.models import CEB, Province, Region, School
from schools.forms import SchoolForm

from .forms import PhonePasswordResetForm
from .models import User


class UserModelTests(TestCase):
    def test_user_string_representation_uses_role_label(self):
        user = User.objects.create_user(
            username='agent.yaagda',
            password='test-pass-123',
            first_name='Awa',
            last_name='Savadogo',
            role=User.Role.REGIONAL_AGENT,
        )

        self.assertIn('Agent régional', str(user))


class ManagedUserViewTests(TestCase):
    def setUp(self):
        self.region = Region.objects.create(code='YAAG', name='Yaagda')
        self.province = Province.objects.create(region=self.region, code='P1', name='Province 1')
        self.ceb = CEB.objects.create(province=self.province, code='CEB1', name='CEB 1')
        self.school = School.objects.create(
            code='E001',
            name='Ecole Pilote',
            province=self.province,
            ceb=self.ceb,
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

    def test_regional_agent_can_create_provincial_user_for_own_region(self):
        self.client.login(username='regional', password='test-pass-123')

        response = self.client.post(
            reverse('accounts:provincial_create'),
            data={
                'username': 'province.nord',
                'first_name': 'Paul',
                'last_name': 'Ouedraogo',
                'email': 'province@example.com',
                'phone_number': '70000000',
                'job_title': 'Agent provincial',
                'is_active': 'on',
                'province': self.province.id,
                'password1': 'test-pass-123',
                'password2': 'test-pass-123',
            },
        )

        self.assertEqual(response.status_code, 302)
        created_user = User.objects.get(username='province.nord')
        self.assertEqual(created_user.role, User.Role.PROVINCIAL_USER)
        self.assertEqual(created_user.region_id, self.region.id)
        self.assertEqual(created_user.province_id, self.province.id)

    def test_provincial_user_can_create_pedagogical_supervisor_for_own_province(self):
        self.client.login(username='provincial', password='test-pass-123')

        response = self.client.post(
            reverse('accounts:supervisor_create'),
            data={
                'username': 'encadreur.nouveau',
                'first_name': 'Aline',
                'last_name': 'Soma',
                'email': 'encadreur@example.com',
                'phone_number': '71000000',
                'job_title': 'Encadreur',
                'is_active': 'on',
                'ceb': self.ceb.id,
                'password1': 'test-pass-123',
                'password2': 'test-pass-123',
            },
        )

        self.assertEqual(response.status_code, 302)
        created_user = User.objects.get(username='encadreur.nouveau')
        self.assertEqual(created_user.role, User.Role.PEDAGOGICAL_SUPERVISOR)
        self.assertEqual(created_user.province_id, self.province.id)
        self.assertEqual(created_user.ceb_id, self.ceb.id)

    def test_pedagogical_supervisor_can_create_school_director_and_assign_school(self):
        self.client.login(username='supervisor', password='test-pass-123')

        response = self.client.post(
            reverse('accounts:director_create'),
            data={
                'username': 'directeur.nouveau',
                'first_name': 'Ali',
                'last_name': 'Kabre',
                'email': 'directeur@example.com',
                'phone_number': '72000000',
                'job_title': "Directeur d'ecole",
                'is_active': 'on',
                'school': self.school.id,
                'password1': 'test-pass-123',
                'password2': 'test-pass-123',
            },
        )

        self.assertEqual(response.status_code, 302)
        created_user = User.objects.get(username='directeur.nouveau')
        self.assertEqual(created_user.role, User.Role.SCHOOL_DIRECTOR)
        self.assertEqual(created_user.ceb_id, self.ceb.id)
        self.school.refresh_from_db()
        self.assertEqual(self.school.director_id, created_user.id)


class PhonePasswordResetTests(TestCase):
    def test_root_login_alias_redirects_to_auth_login_page(self):
        response = self.client.get('/login/')

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('login'))

    def test_user_can_reset_password_with_phone_number(self):
        user = User.objects.create_user(
            username='directeur',
            password='ancien-pass-123',
            phone_number='70000000',
            role=User.Role.SCHOOL_DIRECTOR,
        )

        response = self.client.post(
            reverse('accounts:phone_password_reset'),
            data={
                'username': 'directeur',
                'phone_number': '70000000',
                'new_password1': 'nouveau-pass-456',
                'new_password2': 'nouveau-pass-456',
            },
        )

        user.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('login'))
        self.assertTrue(user.check_password('nouveau-pass-456'))

    def test_reset_is_rejected_when_phone_number_is_invalid(self):
        user = User.objects.create_user(
            username='directeur',
            password='ancien-pass-123',
            phone_number='70000000',
            role=User.Role.SCHOOL_DIRECTOR,
        )

        response = self.client.post(
            reverse('accounts:phone_password_reset'),
            data={
                'username': 'directeur',
                'phone_number': '79999999',
                'new_password1': 'nouveau-pass-456',
                'new_password2': 'nouveau-pass-456',
            },
        )

        user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(user.check_password('ancien-pass-123'))

    def test_phone_reset_page_sets_csrf_cookie(self):
        response = self.client.get(reverse('accounts:phone_password_reset'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('csrftoken', response.cookies)

    def test_invalid_csrf_token_renders_friendly_failure_page(self):
        client = Client(enforce_csrf_checks=True)
        response = client.get(reverse('accounts:phone_password_reset'))
        self.assertIn('csrftoken', response.cookies)

        failed_post = client.post(
            reverse('accounts:phone_password_reset'),
            data={
                'username': 'directeur',
                'phone_number': '70000000',
                'new_password1': 'nouveau-pass-456',
                'new_password2': 'nouveau-pass-456',
                'csrfmiddlewaretoken': 'jeton-invalide',
            },
        )

        self.assertEqual(failed_post.status_code, 403)
        self.assertContains(
            failed_post,
            'Le jeton de sécurité associé au formulaire n&#x27;est plus valide.',
            status_code=403,
        )


class FrenchFormLabelsTests(TestCase):
    def test_key_forms_use_french_labels(self):
        phone_form = PhonePasswordResetForm()
        school_form = SchoolForm()
        activity_form = ActivityForm()

        self.assertEqual(phone_form.fields['phone_number'].label, 'Numéro de téléphone')
        self.assertEqual(school_form.fields['student_capacity'].label, "Capacité d'accueil")
        self.assertEqual(activity_form.fields['reporting_date'].label, 'Date de rapportage')
