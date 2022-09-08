import json
# import qrcode
from io import BytesIO
import django


def _handler(event, context):
    # image = qrcode.make('Some data here')
    message = 'Hello {}!'.format('people')
    # buffered = BytesIO()
    # image.save(buffered, format="JPEG")
    # qr = base64.b64encode(buffered.getvalue())
    body={'message': message, 'event': event, 'qr':None, 'django': str(django.VERSION)}
    return {
        "statusCode": 200,
        "body": json.dumps(body)
    }

import os
import awsgi
from django.core.wsgi import get_wsgi_application
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'helloworld.settings')
application = get_wsgi_application()

def handler(event, context):
    # event['httpMethod'] = 'GET'
    event['path'] = event['path'].replace("api/", "")
    #return {"statusCode": 200, 'body': '{}'}
    return awsgi.response(application, event, context, base64_content_types={"image/png"})

#print(handler({}, None))