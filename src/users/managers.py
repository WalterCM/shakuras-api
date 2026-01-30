from django.contrib.auth.models import BaseUserManager

class UserManager(BaseUserManager):
    def get_test_payload(self):
        return {
            'email': 'test@mail.com',
            'password': '123456',
            'first_name': 'Bob',
            'last_name': 'Ross',
            'nickname': 'Test'
        }

    def create_tag(self, nickname, email):
        """Tag creator. Not used"""
        minimum = 1001
        maximum = 9999
        word = nickname + email
        hashid = (hash(word) % (maximum - minimum)) + minimum
        tag = '{nickname}#{hashid}'.format(
            nickname=nickname, hashid=hashid
        )
        return tag

    def create_user(self, email=None, password=None, nickname=None, **extra_fields):
        """Manager that takes nickname into account"""
        if not email:
            raise ValueError('Users must have an email address')
        if not nickname:
            raise ValueError('User requires a nickname')
        
        user = self.model(
            email=self.normalize_email(email),
            nickname=nickname,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self.db)

        return user

    def create_superuser(self, email=None, password=None, **extra_fields):
        """Creates and saves the superuser"""
        if 'nickname' not in extra_fields:
            extra_fields['nickname'] = 'admin'
            
        user = self.create_user(email, password, **extra_fields)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self.db)

        return user
