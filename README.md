# dvasya

## Django Views for AsyncIO API

Framework for creating asynchronous REST APIs in Django Class-based views style.

* Django URL resolver is implemented for basic and recursive routing
* Class-based views and function views are supported
* Django ORM is not applicable because async connection pool is missing,
but it is possible to use eventloop.run_in_executor() to run SQL queries in
separate thread pool.

== Quick start ==
An example project could be found in testapp module.

1. First, create settings.py file in project root. Like in Django, it will
keep all project settings.

```python
ROOT_URLCONF = "urls"
```

2. As You see, dvasya will search for root url configuration in module urls.
Let's create it.

``python

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