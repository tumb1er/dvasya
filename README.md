# dvasya

## Django Views for AsyncIO API

Framework for creating asynchronous REST APIs in Django Class-based views style.

* Django URL resolver is implemented for basic and recursive routing
* Class-based views and function views are supported
* Django ORM is not applicable because async connection pool is missing,
but it is possible to use eventloop.run_in_executor() to run SQL queries in
separate thread pool.

## Quick start

An example project could be found in testapp module.

### Project settings

First, create settings.py file in project root. Like in Django, it will
keep all project settings.

```python
ROOT_URLCONF = "urls"
```

### Url routing

As You see, dvasya will search for root url configuration in module urls.
Let's create it.

```python
from dvasya.urls import patterns, url, include
from testapp.views import dump_args_view, TestView

included = patterns('',
    url('^test/([\d]+)/', dump_args_view),
    url('^test/(?P<kwarg>[\w]+)/', dump_args_view),
)

urlpatterns = patterns('',
    url('^include/', include('testapp.urls.included')),
    url('^class/', TestView.as_view()),
)
```

So, urls starting with "/include" will be routed to another url configuration
defined by `included` attribute. Rest of path will be used to find a route
in local url configuration.

### View handlers

You need to define some handlers, which will process specific urls.

It could be done with functions:

```python
def example_view(request, *args, **kwargs):
    body = u"<h3>Hello there!</h3>"
    return HttpResponse(body, 200)
```

Or with class-based views:

```python
class ExampleView(View):
    """ And example of simple class-based view."""

    def get(self, request, *args, **kwargs):
        body = u"<h3>Hello there!</h3>"
        return HttpResponse(body, 200)
```

### Run it all

```sh
$> dvasya-manage --no-daemon --settings "testapp.settings"
```

Now you can access test application:
[http://localhost:8080/class/](http://localhost:8080/class/)

### Use it asynchronous

View handlers can be decorated with `asyncio.coroutine` and allow to process
every single request asynchronously.

```python
def async_view(request, *args, **kwargs):
    yield from self.connect_redis()
    result = yield from self.redis.get(SOME_KEY)
    return HttpResponse(json.dumps({"result": result}))
```
