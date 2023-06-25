from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.shortcuts import render, redirect
from django.urls import path

from core.models import Player


class PlayerAdmin(admin.ModelAdmin):
    list_display = ('name', 'team')

    def changelist_view(self, request, extra_context=None):
        if request.method == 'POST' and 'generate_players' in request.POST:
            number_of_players = int(request.POST.get('number_of_players', '0'))
            player_manager = Player.objects
            for _ in range(number_of_players):
                player = player_manager.generate_player()
                player.save()

            self.message_user(request, f'Successfully generated {number_of_players} players.')

            return redirect('admin:core_player_changelist')

        extra_context = extra_context or {}
        extra_context['show_generate_players_input'] = True

        return super().changelist_view(request, extra_context=extra_context)


admin.site.register(Player, PlayerAdmin)
