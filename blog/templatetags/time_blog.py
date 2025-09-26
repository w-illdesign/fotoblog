# blog/templatetags/timeblog.py
from django import template
from blog.utils import publications_time as _publications_time  # importe la logique partagée

register = template.Library()

@register.filter
def publications_time(value):
    return _publications_time(value)