import json
import django
import os
import awsgi
from django.core.wsgi import get_wsgi_application
from django.apps import apps

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'helloworld.settings')
application = get_wsgi_application()

def handler(event, context):
    event['path'] = event['path'].replace("api/", "")
    # User = apps.get_model('auth', 'User')
    # return {"statusCode": 200, "body": json.dumps(dict(users=User.objects.count()))}
    return awsgi.response(application, event, context, base64_content_types={"image/png"})


