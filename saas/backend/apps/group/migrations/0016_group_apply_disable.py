# Generated by Django 3.2.16 on 2023-08-24 03:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('group', '0015_alter_group_hidden'),
    ]

    operations = [
        migrations.AddField(
            model_name='group',
            name='apply_disable',
            field=models.BooleanField(db_index=True, default=False, verbose_name='用户组不可申请'),
        ),
    ]
