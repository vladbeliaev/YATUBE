from http import HTTPStatus

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from ..models import Follow, Group, Post

User = get_user_model()


class PostURLTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='auth')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='Test-slug',
            description='Тестовое описание',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовая группа',
        )


    def setUp(self):
        self.guest_client = Client()
        self.user = User.objects.create_user(username='HasNoName')
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        self.author = PostURLTests.user
        self.authorized_client_author = Client()
        self.authorized_client_author.force_login(self.author)

    def test_urls_uses_correct_template_for_guest_client(self):
        """URL-адрес использует соответствующий шаблон index, group_list,
            profile, post_detail."""
        templates_url_names = {
            '/': 'posts/index.html',
            f'/group/{PostURLTests.group.slug}/': 'posts/group_list.html',
            f'/profile/{PostURLTests.user.username}/': 'posts/profile.html',
            f'/posts/{PostURLTests.post.id}/': 'posts/post_detail.html',
        }
        for address, template in templates_url_names.items():
            with self.subTest(address=address, template=template):
                response = self.guest_client.get(address)
                self.assertTemplateUsed(response, template)

    def test_urls_uses_correct_template_for_authorized_client(self):
        """URL-адрес использует соответствующий шаблон post_edit"""
        templates_url_names = {
            '/create/': 'posts/create_post.html',
            '/follow/': 'posts/follow.html',
        }
        for address, template in templates_url_names.items():
            with self.subTest(address=address, template=template):
                response = self.authorized_client.get(address)
                self.assertTemplateUsed(response, template)

    def test_urls_uses_correct_template_for_author(self):
        """URL-адрес использует соответствующий шаблон post_edit"""
        templates_url_names = {
            f'/posts/{PostURLTests.post.id}/edit/': 'posts/create_post.html',
        }
        for address, template in templates_url_names.items():
            with self.subTest(address=address, template=template):
                response = self.authorized_client_author.get(address)
                self.assertTemplateUsed(response, template)

    def test_unexisting_page(self):
        """Тест несуществующей страницы"""
        address = '/unexisting_page/'
        response = self.guest_client.get(address)
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
