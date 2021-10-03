import json
def handler(event, context):
    message = 'Hello {}!'.format('people')
    body={'message': message, 'event': event}
    return {
        "statusCode": 200,
        "body": json.dumps(body)
    }

