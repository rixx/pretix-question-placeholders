# Generated by Django 3.0.11 on 2021-01-21 10:33

import i18nfield.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("pretix_question_placeholders", "0002_questionplaceholder_slug"),
    ]

    operations = [
        migrations.AlterField(
            model_name="placeholderrule",
            name="content",
            field=i18nfield.fields.I18nTextField(null=True),
        ),
        migrations.AlterField(
            model_name="questionplaceholder",
            name="fallback_content",
            field=i18nfield.fields.I18nTextField(null=True),
        ),
    ]