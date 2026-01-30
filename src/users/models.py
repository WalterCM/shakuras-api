from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils.translation import gettext_lazy as _
from .managers import UserManager

class AbstractUser(AbstractBaseUser, PermissionsMixin):
    """Personalized User abstract model"""
    email = models.EmailField(
        _('email address'),
        unique=True,
        error_messages={'unique': 'A user with that email address already exists.'},
    )
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'email'

    class Meta:
        abstract = True

class User(AbstractUser):
    nickname = models.CharField(max_length=30, unique=True)

    objects = UserManager()

    class Meta:
        db_table = 'core_user'  # Keep the existing table name to avoid data migration issues initially

    @property
    def name(self):
        name = '{first_name} "{nickname}" {last_name}'
        return name.format(
            first_name=self.first_name,
            nickname=self.nickname,
            last_name=self.last_name
        )

    def __str__(self):
        return self.email
