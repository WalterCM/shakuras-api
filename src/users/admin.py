from django.contrib import admin
from core.models import User


class UserAdmin(admin.ModelAdmin):
    list_display = ('name',)


admin.site.register(User, UserAdmin)
