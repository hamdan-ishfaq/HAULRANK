from django.contrib import admin

from .models import Carrier, Driver, Truck

admin.site.register(Carrier)
admin.site.register(Truck)
admin.site.register(Driver)
