from django.http import HttpResponse

def index(request):
    return HttpResponse('<html><body><h1>:)</h1></body></html>')