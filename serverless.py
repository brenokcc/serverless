import os
import io
import json
import zipfile
import boto3


class ServerlessApp():
    def __init__(self, key, secret, name, path, debug=False):
        self.key = key
        self.secret = secret
        self.name = name
        self.path = path
        self.debug = debug
        self.iam = self.get_client('iam')
        self.logs = self.get_client('logs')
        self.lam = self.get_client('lambda')
        self.apigateway = self.get_client('apigateway')

    def log(self, data):
        if self.debug:
            print(data)

    def build(self):
        self.create_role()
        self.create_lambda()
        self.create_api()
        self.deploy_api()

    def get_client(self, name):
        return boto3.client(name, aws_access_key_id=self.key, aws_secret_access_key=self.secret)

    def create_access_key(self, user_name):
        self.iam.create_user(UserName=user_name)
        self.iam.attach_user_policy(
            UserName='user',
            PolicyArn='arn:aws:iam::aws:policy/AdministratorAccess'
        )
        return self.iam.create_access_key(UserName='user')

    def create_role(self):
        doc = {
            'Version': '2012-10-17',
            'Statement': [
                {'Effect': 'Allow', 'Principal': {
                    'Service': ['lambda.amazonaws.com', 'apigateway.amazonaws.com']}, 'Action': 'sts:AssumeRole'
                 }
            ]
        }
        role = self.iam.create_role(
            RoleName=self.name,
            AssumeRolePolicyDocument=json.dumps(doc)
        )
        self.log(role)

    def view_lambda_logs(self):
        return self.logs.filter_log_events(
            logGroupName='/aws/lambda/{}'.format(self.name)
        )

    def pack(self):
        package = io.BytesIO()
        z = zipfile.ZipFile(package, 'w')
        z.write(self.path, self.path)
        z.close()
        return package.getvalue()

    def create_lambda(self):
        role = self.iam.get_role(RoleName=self.name)
        function = self.lam.create_function(
            FunctionName=self.name,
            Runtime='python3.9',
            Role=role['Role']['Arn'],
            Handler='hello.handler',
            Code={'ZipFile': self.pack()}
        )
        self.log(function)
        doc = {'Version': '2012-10-17', 'Statement': [
            {'Effect': 'Allow', 'Action': 'lambda:InvokeFunction', 'Resource': function['FunctionArn']}]}
        policy = self.iam.create_policy(
            PolicyName='Invoke{}'.format(function['FunctionName']),
            PolicyDocument=json.dumps(doc)
        )
        self.log(policy)
        attach = self.iam.attach_role_policy(
            RoleName=self.name,
            PolicyArn=policy['Policy']['Arn']
        )
        self.log(attach)

    def update_lambda(self):
        self.lam.update_function_code(FunctionName=self.name, ZipFile=self.pack())

    def invoke_lambda(self, payload):
        response = self.lam.invoke(
            FunctionName=self.name,
            InvocationType='RequestResponse',
            LogType='Tail',
            Payload=json.dumps(payload)
        )
        response['StatusCode']
        data = json.loads(response['Payload'].read().decode())
        return data

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
        self.get_url()

    def get_api(self, name):
        for api in self.apigateway.get_rest_apis()['items']:
            if api['name'] == name:
                return api
        return None

    def get_url(self, stage_name='prod'):
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

    def delete_lambda(self):
        response = self.lam.delete_function(FunctionName=self.name)
        self.log(response)

    def delete_roles(self):
        for policy in self.iam.list_attached_role_policies(RoleName=self.name)['AttachedPolicies']:
            response = self.iam.detach_role_policy(RoleName=self.name, PolicyArn=policy['PolicyArn'])
            self.log(response)
            response = self.iam.delete_policy(PolicyArn=policy['PolicyArn'])
            self.log(response)
        response = self.iam.delete_role(RoleName=self.name)
        self.log(response)

    def destroy(self):
        self.delete_api()
        self.delete_lambda()
        self.delete_roles()


if __name__ == '__main__':
    app = ServerlessApp(os.environ['KEY'], os.environ['SECRET'], 'HelloWorld', 'hello.py', debug=True)
    # app.create_role()
    # app.create_lambda()
    # app.create_api()
    # app.update_lambda()
    # app.delete_api()
    # app.delete_lambda()
    # app.delete_roles()
