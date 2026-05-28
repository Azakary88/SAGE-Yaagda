from django.db import migrations


def seed_innovations(apps, schema_editor):
    Innovation = apps.get_model('innovations', 'Innovation')
    defaults = [
        {
            'name': 'Jardinage',
            'slug': 'jardinage',
            'category': 'TRADES',
            'description': 'Suivi des activites de jardinage scolaire.',
        },
        {
            'name': 'Elevage',
            'slug': 'elevage',
            'category': 'TRADES',
            'description': 'Suivi des activites d elevage scolaire.',
        },
        {
            'name': 'Artisanat',
            'slug': 'artisanat',
            'category': 'TRADES',
            'description': 'Suivi des ateliers d artisanat scolaire.',
        },
        {
            'name': 'TIC',
            'slug': 'tic',
            'category': 'ICT',
            'description': 'Suivi de l integration des TIC dans les ecoles.',
        },
        {
            'name': 'Anglais',
            'slug': 'anglais',
            'category': 'ENGLISH',
            'description': 'Suivi de l enseignement de l anglais.',
        },
    ]

    for item in defaults:
        Innovation.objects.update_or_create(
            slug=item['slug'],
            defaults=item,
        )


def unseed_innovations(apps, schema_editor):
    Innovation = apps.get_model('innovations', 'Innovation')
    Innovation.objects.filter(slug__in=['jardinage', 'elevage', 'artisanat', 'tic', 'anglais']).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('innovations', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_innovations, unseed_innovations),
    ]
