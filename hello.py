import json
import qrcode
from io import BytesIO


def handler(event, context):
    # image = qrcode.make('Some data here')
    message = 'Hello {}!'.format('people')
    # buffered = BytesIO()
    # image.save(buffered, format="JPEG")
    # qr = base64.b64encode(buffered.getvalue())
    body={'message': message, 'event': event, 'qr':None}
    return {
        "statusCode": 200,
        "body": json.dumps(body)
    }


#print(handler({}, None))