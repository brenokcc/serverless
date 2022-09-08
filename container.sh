docker run --rm -e PYTHONPATH=/opt/python/ -v "$(pwd)/lib:/opt/python" -v "$(pwd)/python/helloworld:/opt/helloworld" -p 8000:8000 -it --entrypoint sh public.ecr.aws/lambda/python:3.8

#pip install --only-binary=:all: Django -t /opt/python


#curl -XPOST "http://localhost:8000/2015-03-31/functions/function/invocations" -d '{"payload":"hello world!"}'


docker run --rm -e PYTHONPATH=/opt/python/ -v "$(pwd)/lib:/opt/python" -v "$(pwd)/python/helloworld:/opt/python/helloworld" -p 9000:8080 -it -v "$(pwd)/app.py:/var/task/app.py" public.ecr.aws/lambda/python:3.8 app.handler
