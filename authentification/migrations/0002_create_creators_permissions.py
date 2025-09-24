from django.db import migrations

def create_groups(apps, schema_editor):
    User = apps.get_model('authentification', 'User')
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    # Récupération des permissions add_blog et delete_blog
    add_blog = Permission.objects.get(codename='add_blog')
    delete_blog = Permission.objects.get(codename='delete_blog')

    # Création ou récupération du groupe creators
    creators, created = Group.objects.get_or_create(name='creators')
    creators.permissions.set([add_blog, delete_blog])

    # Ajout des utilisateurs ayant role='Creator' au groupe creators
    for user in User.objects.all():
        if user.role == 'Creator' and not creators.user_set.filter(id=user.id).exists():
            creators.user_set.add(user)

class Migration(migrations.Migration):

    dependencies = [
        ('authentification', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_groups),
    ]