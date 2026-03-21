#!/usr/bin/env bash
set -o errexit

export DJANGO_SETTINGS_MODULE=waste_project.settings

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate