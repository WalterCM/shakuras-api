
from django.db import models
from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.models import BaseUserManager
from django.contrib.auth.models import PermissionsMixin

from django.utils.translation import gettext_lazy as _


# User
class UserManager(BaseUserManager):
    def get_test_payload(self):
        return {
            'email': 'test@mail.com',
            'password': '123456',
            'first_name': 'Bob',
            'last_name': 'Ross'
        }

    def create_user(self, email=None, password=None, **extra_fields):
        """Creates and saves the users"""
        if not email:
            raise ValueError('Users must have an email address')
        user = self.model(
            email=self.normalize_email(email),
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self.db)

        return user

    def create_superuser(self, email=None, password=None,  **extra_fields):
        """Creates and saves the superuser"""
        user = self.create_user(email, password, **extra_fields)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self.db)

        return user


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
