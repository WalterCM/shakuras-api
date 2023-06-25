from django.contrib import admin
from core.models import Player


class PlayerAdmin(admin.ModelAdmin):
    list_display = ('name', 'team')


admin.site.register(Player, PlayerAdmin)
