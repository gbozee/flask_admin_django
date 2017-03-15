### Pluggable django ModelView for use with Flask Admin

to install

```pip install -e git+https://github.com/gbozee/flask_admin_django.git@master#egg=contrib_django```

and set up  `flask-admin`

```
import os
from flask import Flask, jsonify
from flask_admin import Admin
from todolist.models import TodoItem  # a django model
from contrib_django.view import DjangoModelView as ModelView

app = Flask(__name__)
# Create admin with custom base template
admin = Admin(
    app,
    'Example: Layout-BS3',
    base_template='layout.html',
    template_mode='bootstrap3')


class CustomView(ModelView):
    list_template = 'list.html'
    create_template = 'create.html'
    edit_template = 'edit.html'
    column_searchable_list = ['title']



admin.add_view(CustomView(TodoItem))

```

**This is still in development and certainly contain bugs. but it is a work in progress**

