import datetime
import os
import io
import json
import zipfile
import boto3
import shutil
from dotenv import load_dotenv
from botocore.exceptions import ClientError
from boto3.dynamodb.types import STRING
from uuid import uuid1
load_dotenv()



class ServerlessApp():
    def __init__(self, key, secret, region_name, name, path, debug=True):
        self.key = key
        self.secret = secret
        self.region_name = region_name
        self.name = name
        self.path = path
        self.debug = debug
        self.iam = self.get_client('iam')
        self.logs = self.get_client('logs')
        self.lam = self.get_client('lambda')
        self.apigateway = self.get_client('apigateway')
        self.dynamodb = self.get_resource('dynamodb')
        self.runtime = 'python3.8'

    def log(self, data):
        if self.debug:
            print(data)

    def build(self):
        self.create_role()
        self.create_lambda()
        self.create_api()
        self.deploy_api()

    def get_client(self, name):
        return boto3.client(name, aws_access_key_id=self.key, aws_secret_access_key=self.secret, region_name=self.region_name)

    def get_resource(self, name):
        return boto3.resource(name, aws_access_key_id=self.key, aws_secret_access_key=self.secret, region_name=self.region_name)

    def get_cost(self):
        response = self.get_client('ce').get_cost_and_usage(
            TimePeriod={
                'Start': '2022-09-01',
                'End': datetime.date.today().strftime('%Y-%m-%d')
            },
            Granularity='MONTHLY',
            Metrics=[
                'AmortizedCost',
            ]
        )
        self.log(response)
        return response

    # ACCESS KEY
    def create_access_key(self, user_name):
        self.iam.create_user(UserName=user_name)
        self.iam.attach_user_policy(
            UserName='user',
            PolicyArn='arn:aws:iam::aws:policy/AdministratorAccess'
        )
        return self.iam.create_access_key(UserName='user')

    # ROLES
    def create_role(self):
        try:
            role = self.iam.get_role(RoleName=self.name)
            self.log(role)
            return role
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchEntity':
                self.log('Creating role...')
                doc = {
                    'Version': '2012-10-17',
                    'Statement': [
                        {
                            'Effect': 'Allow',
                            'Principal': {
                                'Service': ['lambda.amazonaws.com', 'apigateway.amazonaws.com', 's3.amazonaws.com']
                            },
                            'Action': 'sts:AssumeRole'
                        }
                    ]
                }
                role = self.iam.create_role(
                    RoleName=self.name,
                    AssumeRolePolicyDocument=json.dumps(doc)
                )
                self.log(role)
                return role

    def delete_role(self):
        for policy in self.iam.list_attached_role_policies(RoleName=self.name)['AttachedPolicies']:
            response = self.iam.detach_role_policy(RoleName=self.name, PolicyArn=policy['PolicyArn'])
            self.log(response)
            response = self.iam.delete_policy(PolicyArn=policy['PolicyArn'])
            self.log(response)
        response = self.iam.delete_role(RoleName=self.name)
        self.log(response)

    # S3 BUCKET
    def get_bucket_name(self):
        return '{}-bckt'.format(self.name.lower())

    def create_bucket(self):
        s3 = self.get_client('s3')
        self.log('Creating bucket...')
        try:
            response = s3.create_bucket(
                Bucket=self.get_bucket_name()
            )
            self.log(response)
            return response
        except ClientError as e:
            if e.response['Error']['Code'] == 'EntityAlreadyExists':
                self.log('Bucket already exists!')
            else:
                raise e

    def create_bucket_policy(self):
        doc = {
            'Version': '2012-10-17',
            'Statement': [{
                'Effect': 'Allow',
                'Action': ['s3:GetObject', 's3:ListBucket', 's3:PutObject'],
                'Resource': 'arn:aws:s3:::{}'.format(self.get_bucket_name())
            }]
        }
        try:
            self.log('Creating bucket policy...')
            policy = self.iam.create_policy(
                PolicyName='AccessBucket{}'.format(self.get_bucket_name()),
                PolicyDocument=json.dumps(doc)
            )
            self.log(policy)
            self.log('Attaching bucket policy...')
            attach = self.iam.attach_role_policy(
                RoleName=self.name,
                PolicyArn=policy['Policy']['Arn']
            )
            self.log(attach)
        except ClientError as e:
            if e.response['Error']['Code'] == 'EntityAlreadyExists':
                self.log('Bucket policy already exists!')
            else:
                raise e

    def upload_file(self, filename):
        s3 = self.get_client('s3')
        response = s3.upload_file(filename, self.get_bucket_name(), filename)
        print(response)

    def empty_bucket(self):
        s3 = self.get_resource('s3')
        bucket = s3.Bucket(self.get_bucket_name())
        response = bucket.objects.all().delete()
        self.log(response)

    def delete_bucket(self):
        s3 = self.get_client('s3')
        response = s3.delete_bucket(Bucket=self.get_bucket_name())
        self.log(response)

    # LAMBDA
    def get_lambda_name(self):
        return self.name

    def pack(self):
        package = io.BytesIO()
        z = zipfile.ZipFile(package, 'w')
        z.write(self.path, self.path)
        z.close()
        return package.getvalue()

    def create_lambda(self):
        self.log('Creating lambda...')
        role = self.iam.get_role(RoleName=self.name)
        try:
            function = self.lam.get_function(FunctionName=self.get_lambda_name())
            self.log('Lambda already exists!')
            return function
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                function = self.lam.create_function(
                    FunctionName=self.get_lambda_name(),
                    Runtime=self.runtime,
                    Role=role['Role']['Arn'],
                    Handler='app.handler',
                    Code={'ZipFile': self.pack()}
                )
                self.log(function)
                return function
            else:
                raise e

    def create_lambda_policy(self):
        response = self.lam.get_function(FunctionName=self.get_lambda_name())
        doc = {
            'Version': '2012-10-17',
            'Statement': [{
                'Effect': 'Allow',
                'Action': 'lambda:InvokeFunction',
                'Resource': response['Configuration']['FunctionArn']
            }]
        }
        try:
            self.log('Creating lambda policy...')
            policy = self.iam.create_policy(
                PolicyName='Invoke{}'.format(response['Configuration']['FunctionName']),
                PolicyDocument=json.dumps(doc)
            )
            self.log(policy)
            self.log('Attaching lamba policy...')
            attach = self.iam.attach_role_policy(
                RoleName=self.name,
                PolicyArn=policy['Policy']['Arn']
            )
            self.log(attach)
        except ClientError as e:
            if e.response['Error']['Code'] == 'EntityAlreadyExists':
                self.log('Lambda policy already exists!')
            else:
                raise e

    def create_lambda_layer(self, **modules):
        for name, module in modules.items():
            layer_dir = 'layer/{}/python'.format(name)
            os.makedirs(layer_dir, exist_ok=True)
            os.system('pip install --platform manylinux1_x86_64 --only-binary=:all: {} -t {}'.format(module, layer_dir))

    def upload_lamba_layer(self, *names):
        for name in names:
            file_name = '{}.zip'.format(name)
            shutil.make_archive(name, 'zip', 'layer/{}'.format(name))
            self.log('Publishing layer {}...'.format(name))
            response = self.lam.publish_layer_version(
                LayerName=name,
                Description='Layer for {}'.format(name),
                Content={'ZipFile': open(file_name, 'r+b').read()},
                CompatibleRuntimes=[self.runtime],
                LicenseInfo='N/A'
            )
            self.log(response)
            return
            self.log('Updating lambda layers...')
            response = self.lam.update_function_configuration(FunctionName=self.name, Layers=[response['LayerVersionArn']])
            self.log(response)

    def update_lambda_code(self):
        response = self.lam.update_function_code(
            FunctionName=self.name, ZipFile=self.pack()
        )
        self.log(response)

    def invoke_lambda(self, payload):
        response = self.lam.invoke(
            FunctionName=self.name,
            InvocationType='RequestResponse',
            LogType='Tail',
            Payload=json.dumps(payload)
        )
        response['StatusCode']
        data = json.loads(response['Payload'].read().decode())
        self.log(data)
        return data

    def view_lambda_logs(self):
        return self.logs.filter_log_events(
            logGroupName='/aws/lambda/{}'.format(self.name)
        )

    def delete_lambda_layer(self):
        response = self.lam.list_layers(CompatibleRuntime=self.runtime)
        for layer in response['Layers']:
            if layer['LayerName'] == self.name:
                print(layer)
        response = self.lam.delete_layer_version(
            LayerName=self.name,
            VersionNumber=1
        )
        self.log(response)


    def delete_lambda(self):
        response = self.lam.delete_function(FunctionName=self.name)
        self.log(response)

    # DYNAMODB
    def create_table(self):
        breakpoint()
        params = {
            'TableName': self.name,
            'KeySchema': [
                {'AttributeName': 'pk', 'KeyType': 'HASH'},
                {'AttributeName': 'model', 'KeyType': 'RANGE'}
            ],
            'AttributeDefinitions': [
                {'AttributeName': 'pk', 'AttributeType': 'S'},
                {'AttributeName': 'model', 'AttributeType': 'S'}
            ],
            'ProvisionedThroughput': {
                'ReadCapacityUnits': 1,
                'WriteCapacityUnits': 1
            }
        }
        self.log(params)
        try:
            table = self.dynamodb.create_table(**params)
            table.wait_until_exists()
        except BaseException as e:
            if 'Table already exists' in e.response['Error']['Message']:
                table = self.dynamodb.Table(self.name)
            else:
                raise e
        return table

    def create_index(self, attr_name, attr_type='S'):
        attrs = [
            {'AttributeName': 'model', 'AttributeType': 'S'},
            {"AttributeName": attr_name, "AttributeType": attr_type}
        ]
        indexes = [
            {"Create":
                {
                    "IndexName": attr_name,
                    "KeySchema": [
                        {
                            "AttributeName": "model",
                            "KeyType": "HASH"
                        },
                        {
                            "AttributeName": "sexo",
                            "KeyType": "RANGE"
                        }
                    ],
                    'Projection': {'ProjectionType': "KEYS_ONLY"},
                    'ProvisionedThroughput': {'ReadCapacityUnits': 2, 'WriteCapacityUnits': 2}
                }
            }
        ]
        table = self.dynamodb.Table(self.name)
        response = table.update(AttributeDefinitions=attrs, GlobalSecondaryIndexUpdates=indexes)
        print(response)
        return response

    def delete_table(self):
        try:
            table = self.dynamodb.Table(self.name)
            table.delete()
        except BaseException as e:
            if not 'Table: {} not found'.format(self.name) in e.response['Error']['Message']:
                raise e

    def create_api(self):
        lam = self.get_client('lambda')
        api = self.apigateway.create_rest_api(name=self.name)
        root = self.apigateway.get_resources(restApiId=api['id'])['items'][0]
        resource = self.apigateway.create_resource(restApiId=api['id'], parentId=root['id'], pathPart='{proxy+}')
        self.log(resource)
        put_method = self.apigateway.put_method(
            restApiId=api['id'], resourceId=resource['id'], httpMethod='ANY', authorizationType='NONE',
        )
        self.log(put_method)
        put_method_response = self.apigateway.put_method_response(
            restApiId=api['id'], resourceId=resource['id'], httpMethod='ANY', statusCode='200'
        )
        self.log(put_method_response)
        function = lam.get_function(FunctionName=self.name)
        uri = 'arn:aws:apigateway:{}:lambda:path/2015-03-31/functions/{}/invocations'.format(
            self.apigateway.meta.region_name, function['Configuration']['FunctionArn']
        )
        self.log(uri)
        put_integration = self.apigateway.put_integration(
            restApiId=api['id'],
            resourceId=resource['id'],
            httpMethod='ANY',
            type='AWS_PROXY',
            integrationHttpMethod='POST',
            uri=uri,
            credentials=function['Configuration']['Role'],
        )
        self.log(put_integration)
        put_integration_response = self.apigateway.put_integration_response(
            restApiId=api['id'],
            resourceId=resource['id'],
            httpMethod='ANY',
            statusCode='200',
            selectionPattern=''
        )
        self.log(put_integration_response)
        deployment = self.apigateway.create_deployment(restApiId=api['id'], stageName='prod')
        self.log(deployment)
        return self.get_api_url()

    def get_api(self, name):
        for api in self.apigateway.get_rest_apis()['items']:
            if api['name'] == name:
                return api
        return None

    def get_api_url(self, stage_name='prod'):
        api = self.get_api(self.name)
        url = 'https://{}.execute-api.{}.amazonaws.com/{}/api/'.format(
            api['id'], self.apigateway.meta.region_name, stage_name
        )
        self.log(url)
        return url

    def delete_api(self):
        api = self.get_api(self.name)
        response = self.apigateway.delete_rest_api(restApiId=api['id'])
        self.log(response)

    def destroy(self):
        self.delete_api()
        self.delete_lambda()
        self.delete_roles()


if __name__ == '__main__':
    app = ServerlessApp(os.environ['KEY'], os.environ['SECRET'], os.environ['REGION'], 'HelloWorld', 'app.py', debug=True)

    # app.create_role()
    # app.delete_role()

    # app.create_bucket()
    # app.create_bucket_policy()
    # app.upload_file('README.md')
    # app.empty_bucket()
    # app.delete_bucket()

    # app.create_lambda()
    # app.create_lambda_policy()
    # app.create_lambda_layer(django=('Django==3.2', 'aws-wsgi'))
    # app.create_lambda_layer(pillow=('Pillow==8.0'))
    # app.create_lambda_layer(postgres=('psycopg2-binary==2.7.5'))
    # app.upload_lamba_layer('postgres')
    # app.update_lambda_code()
    app.invoke_lambda(dict(a=1, b=2))
    # app.delete_lambda_layer()
    # app.delete_lambda()

    # app.create_api()
    # app.get_api_url()
    # app.delete_api()

    # app.create_table()
    # app.create_index('sexo')
    # app.delete_table()

    # app.get_cost()