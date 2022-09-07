import json
import os
from collections import UserDict
from collections.abc import Sequence
from uuid import uuid1

import boto3
from boto3.dynamodb.conditions import Key, Attr
from dotenv import load_dotenv

load_dotenv()


dynamodb = boto3.resource(
    'dynamodb',
    aws_access_key_id=os.environ['KEY'],
    aws_secret_access_key=os.environ['SECRET']
)

table = dynamodb.Table(os.environ['APP'])

OPERATORS = {
    'eq': '=',
    'lt': '<',
    'lte': '<=',
    'gt': '>',
    'gte': '>=',
}


def where(k, v):
    tokens = k.split('__')
    token = tokens.pop()
    op = OPERATORS.get(token)
    if op is None:
        op = '='
        tokens.append(token)
    return '{} {} {}'.format('__'.join(tokens), op, v)

def expression(k, v):
    name = 'eq'
    tokens = k.split('__')
    token = tokens.pop()
    if token in OPERATORS.keys():
        name = token
    else:
        tokens.append(token)
    func = getattr(Attr('.'.join(tokens)), name)
    return func(v)


class ClassPropertyDescriptor(object):

    def __init__(self, fget, fset=None):
        self.fget = fget
        self.fset = fset

    def __get__(self, obj, klass=None):
        if klass is None:
            klass = type(obj)
        return self.fget.__get__(obj, klass)()

    def __set__(self, obj, value):
        if not self.fset:
            raise AttributeError("can't set attribute")
        type_ = type(obj)
        return self.fset.__get__(obj, type_)(value)

    def setter(self, func):
        if not isinstance(func, (classmethod, staticmethod)):
            func = classmethod(func)
        self.fset = func
        return self


def classproperty(func):
    if not isinstance(func, (classmethod, staticmethod)):
        func = classmethod(func)
    return ClassPropertyDescriptor(func)


class QuerySet(Sequence):
    def __init__(self, model):
        self.items = None
        self.model = model
        self.exp = expression('model', self.model.__name__)
        self.attrs = None
        self.max = 10
        self.total = 0
        self.where = ['model = {}'.format(self.model.__name__)]

    def clone(self):
        qs = QuerySet(self.model)
        qs.exp = self.exp
        qs.attrs = self.attrs
        qs.where = self.where
        return qs

    @property
    def query(self):
        return 'SELECT {} FROM {} WHERE {}'.format(self.attrs or '*', table.name, ' AND '.join(self.where))

    def put(self, item):
        pk = uuid1().hex
        item.update(pk=pk, model=self.model.__name__)
        response = table.put_item(Item=item)
        return pk if response['ResponseMetadata']['HTTPStatusCode'] == 200 else None

    def create(self, **kwargs):
        pk = self.put(kwargs)
        return self.model(**kwargs) if pk else None

    def get(self, pk):
        response = table.get_item(Key={'pk': pk, 'model': self.model.__name__})
        return self.model(**response.get('Item'))

    def filter(self, **kwargs):
        for k, v in kwargs.items():
            self.where.append(where(k, v))
            self.exp = self.exp & expression(k, v)
        return self.clone()

    def exclude(self, **kwargs):
        for k, v in kwargs.items():
            self.where.append(where(k, v))
            self.exp = self.exp & ~ expression(k, v)
        return self.clone()

    def filter2(self, **kwargs):
        response = table.query(
            IndexName='sexo',
            KeyConditionExpression=Key('model').eq(self.model.__name__) & Key('sexo').eq('M'),
            ReturnConsumedCapacity='TOTAL'
        )
        print(response)

    def values(self, *attrs):
        self.attrs = ','.join(attr.replace('__', '.') for attr in attrs)
        return self.clone()

    def values_list(self, *attrs, flat=False):
        items = []
        values = self.values(*attrs)
        for value in values:
            if flat:
                items.append(value.get(attrs[0]))
            else:
                l = []
                for k in attrs:
                    l.append(value.get(k))
                items.append(l)
        return items

    def limit(self, max):
        self.max = max
        return self

    def first(self):
        return self[0] if len(self) else None

    def delete(self):
        with table.batch_writer() as batch:
            for pk in self.values_list('pk', flat=True):
                batch.delete_item(Key={'pk': pk, 'model': self.model.__name__})

    def __getitem__(self, index):
        return self.scan().items[index]

    def __len__(self):
        return len(self.scan().items)

    def __or__(self, other):
        qs = self.clone()
        qs.exp = self.exp | other.exp
        qs.where = ['(({}) OR ({}))'.format(' AND '.join(self.where), ' AND '.join(other.where))]
        return qs

    def fetch(self, pks):
        response = dynamodb.batch_get_item(
            RequestItems={
                os.environ['APP']: {
                    'Keys': [
                        {'pk': pk, 'model': self.model.__name__} for pk in pks
                    ], 'ConsistentRead': False
                }
            },
            ReturnConsumedCapacity='TOTAL'
        )
        print(response)

    def scan(self):
        if self.items is None:
            print('Scanning...')
            kwargs = dict(FilterExpression=self.exp, Limit=self.max, ReturnConsumedCapacity='TOTAL')
            if self.attrs:
                kwargs.update(ProjectionExpression=self.attrs),
            response = table.scan(**kwargs)
            print(response)
            self.total = response['ScannedCount'] + response['Count']
            self.items = [self.model(**item) for item in response['Items']]
        return self

    def all(self):
        return self

    def count(self):
        return len(self)

    def __str__(self):
        return str(self.scan().items)
        return json.dumps([item.data for item in self.items], indent=2, ensure_ascii=False, use_decimal=True)



class Model(UserDict):

    def __init__(self, **data):
        self.data = data
        self.changes = {}

    @classproperty
    def objects(cls) -> QuerySet:
        return QuerySet(cls)

    def __setitem__(self, key, item):
        super().__setitem__(key, item)
        self.changes[key] = item

    def save(self):
        if self.changes:
            self.update(**self.changes)

    def delete(self):
        response = table.delete_item(Key={'pk': self['pk'], 'model': type(self).__name__})
        return response['ResponseMetadata']['HTTPStatusCode'] == 200

    def __str__(self):
        return str(self.data)
        return json.dumps(self.data, indent=2, ensure_ascii=False, use_decimal=True)

    def update(self, **kwargs):
        update_expressions = []
        update_expression_names = {}
        update_expression_values = {}
        for k, v in kwargs.items():
            update_attr_key = '#{}'.format(k)
            update_value_key = ':{}'.format(k)
            update_expressions.append('{} = {}'.format(update_attr_key, update_value_key))
            update_expression_names[update_attr_key] = k
            update_expression_values[update_value_key] = v
        update_expression = 'set {}'.format(','.join(update_expressions))
        print(update_expression)
        print(update_expression_names)
        print(update_expression_values)
        table.update_item(
            Key={'pk': self['pk'], 'model': type(self).__name__},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=update_expression_values,
            ExpressionAttributeNames=update_expression_names,
            ReturnValues="UPDATED_NEW"
        )
