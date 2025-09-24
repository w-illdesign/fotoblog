# blog/templatetags/timeblog.py
from django import template
from blog.utils import facebook_time as _facebook_time  # importe la logique partagée

register = template.Library()

@register.filter
def facebook_time(value):
    return _facebook_time(value)