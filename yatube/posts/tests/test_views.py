import shutil
import tempfile

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ..models import Follow, Group, Post

User = get_user_model()
TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostViewsTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        uploaded = SimpleUploadedFile(
            name='small.gif',
            content=small_gif,
            content_type='image/gif',
        )
        cls.user = User.objects.create_user(username='auth')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='Test-slug',
            description='Тестовое описание',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый текст',
            group=cls.group,
            image=uploaded,
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.guest_client = Client()
        self.user = User.objects.create_user(username='HasNoName')
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        self.author = PostViewsTests.user
        self.authorized_client_author = Client()
        self.authorized_client_author.force_login(self.author)
        cache.clear()

    def test_new_post(self):
        """Проверяет, что если при создании поста указать группу, то этот пост
        появляется на главной странице сайта, на странице выбранной группы, в
        профайле пользователя. Проверьте, что этот пост не попал в группу, для
        которой не был предназначен."""
        new_group = Group.objects.create(
            title='Новая тестовая группа',
            slug='New-test-slug',
            description='Новое тестовое описание',
        )
        new_post = Post.objects.create(
            text='new post text',
            author=self.user,
            group=new_group,
        )
        data_urls = [
            reverse('posts:index'),
            reverse('posts:group_list', kwargs={'slug': new_group.slug}),
            reverse('posts:profile', kwargs={'username': self.user.username}),
        ]
        for name in data_urls:
            with self.subTest(name=name):
                response = self.authorized_client.get(name)
                self.assertEqual(response.context['page_obj'][0], new_post)
        response = self.authorized_client_author.get(
            reverse('posts:profile', kwargs={
                'username': PostViewsTests.user.username}
            )
        )
        self.assertNotEqual(response.context['page_obj'][0], new_post)

    def test_pages_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        # Собираем в словарь пары "имя_html_шаблона: reverse(name)"
        slug = PostViewsTests.group.slug
        username = self.author.username
        post_id = PostViewsTests.post.id
        templates_pages_names = {
            reverse('posts:group_list', kwargs={'slug': slug}): (
                'posts/group_list.html'),
            reverse('posts:profile', kwargs={'username': username}): (
                'posts/profile.html'),
            reverse('posts:post_detail', kwargs={'post_id': post_id}): (
                'posts/post_detail.html'),
            reverse('posts:post_create'): (
                'posts/create_post.html'),
            reverse('posts:post_edit', kwargs={'post_id': post_id}): (
                'posts/create_post.html'),
        }

        for reverse_name, template in templates_pages_names.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client_author.get(reverse_name)
                self.assertTemplateUsed(response, template)

    def test_home_page_show_correct_context(self):
        """Шаблон index сформирован с правильным контекстом."""
        response = self.authorized_client_author.get(reverse('posts:index'))
        first_object = response.context['page_obj'][0]
        post_text_0 = first_object.text
        post_author_0 = first_object.author
        post_group_0 = first_object.group
        post_image_0 = first_object.image
        self.assertEqual(post_text_0, PostViewsTests.post.text)
        self.assertEqual(post_author_0, PostViewsTests.user)
        self.assertEqual(post_group_0, PostViewsTests.group)
        self.assertEqual(post_image_0, PostViewsTests.post.image)

    def test_group_list_show_correct_context(self):
        """Шаблон group_list сформирован с правильным контекстом."""
        response = self.authorized_client_author.get(
            reverse('posts:group_list', args=(PostViewsTests.group.slug,))
        )
        self.assertIsInstance(response.context['page_obj'][0], Post)
        self.assertEqual(response.context['group'], PostViewsTests.group)

    def test_profile_show_correct_context(self):
        """Шаблон profile сформирован с правильным контекстом."""
        response = self.authorized_client_author.get(
            reverse('posts:profile', args=(PostViewsTests.user.username,))
        )
        self.assertIsInstance(response.context['page_obj'][0], Post)
        self.assertEqual(response.context['profile'], PostViewsTests.user)

    def test_post_detail_show_correct_context(self):
        """Шаблон post_detail сформирован с правильным контекстом."""
        response = self.authorized_client_author.get(
            reverse('posts:post_detail', args=(PostViewsTests.post.pk,))
        )
        self.assertEqual(response.context['post'], PostViewsTests.post)

    def test_create_post(self):
        """Шаблон create_post сформирован с правильным контекстом.
        Если позьзователь не авторизован,
        происходит redirect на страницу авторизации."""
        response = self.authorized_client_author.get(
            reverse('posts:post_create')
        )
        form_fields = {
            'text': forms.fields.CharField,
            'group': forms.fields.ChoiceField
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get('form').fields.get(value)
                self.assertIsInstance(form_field, expected)
        next = '?next='
        response = self.guest_client.get(
            reverse('posts:post_create')
        )
        self.assertRedirects(
            response,
            reverse('users:login') + next + reverse('posts:post_create')
        )

    def test_post_edit(self):
        """Шаблон post_edit сформирован с правильным контекстом.
        Если позьзователь не авторизован,
        происходит redirect на страницу авторизации.
        Если пользователь не является автором,
        происходит redirect на страницу просмотра поста."""
        response = self.authorized_client_author.get(
            reverse('posts:post_edit', args=(PostViewsTests.post.pk,))
        )
        form_fields = {
            'text': forms.fields.CharField,
            'group': forms.fields.ChoiceField
        }
        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get('form').fields.get(value)
                self.assertIsInstance(form_field, expected)
        self.assertEqual(response.context['post_id'], PostViewsTests.post.pk)
        next = '?next='
        reverse_post_edit_with_arg = reverse(
            'posts:post_edit',
            args=(PostViewsTests.post.pk,)
        )
        response = self.guest_client.get(
            reverse('posts:post_edit', args=(PostViewsTests.post.pk,))
        )
        self.assertRedirects(
            response,
            reverse('users:login') + next + reverse_post_edit_with_arg
        )
        response = self.authorized_client.get(
            reverse('posts:post_edit', args=(PostViewsTests.post.pk,))
        )
        self.assertRedirects(response, f'/posts/{PostViewsTests.post.pk}/')

    def test_caches_on_index_page(self):
        """"Проверка кэша на странице index"""
        new_post = Post.objects.create(
            author=self.user,
            text='Тестовый текст поста при тестировании кэша',
        )
        response = self.guest_client.get(reverse('posts:index'))
        new_post.delete()
        self.assertContains(response, new_post.text)
        cache.clear()
        response = self.guest_client.get(reverse('posts:index'))
        self.assertNotContains(response, new_post.text)


class FollowViewsTests(TestCase):
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
            text='Тестовый текст',
            group=cls.group,
        )

    def setUp(self):
        self.guest_client = Client()
        self.user = User.objects.create_user(username='HasNoName')
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        self.author = FollowViewsTests.user
        self.authorized_client_author = Client()
        self.authorized_client_author.force_login(self.author)
        cache.clear()

    def test_auth_user_can_follow(self):
        """Авторизованный пользователь может подписываться на
        других пользователей"""
        post = Post.objects.create(
            author=FollowViewsTests.user,
            text='new post  for test follow',
        )
        Follow.objects.create(
            user=self.user,
            author=FollowViewsTests.user
        )
        response = self.authorized_client.get(reverse('posts:follow_index'))
        post_context = response.context.get('page_obj')
        self.assertIn(post, post_context)

    def test_auth_user_can_unfollow_authors(self):
        """Авторизованный пользователь может удалять других
        пользователей из подписок"""
        post = Post.objects.create(
            author=FollowViewsTests.user,
            text='new post  for test unfollow',
        )
        follow = Follow.objects.create(
            user=self.user,
            author=FollowViewsTests.user
        )
        follow.delete()
        response = self.authorized_client.get(reverse('posts:follow_index'))
        post_context = response.context.get('page_obj')
        self.assertNotIn(post, post_context)

    def test_new_post_on_folowers_lent(self):
        """Новая запись пользователя появляется в ленте тех,
        кто на него подписан"""
        post = Post.objects.create(
            author=FollowViewsTests.user,
            text='new post  for test follow',
        )
        Follow.objects.create(
            user=self.user,
            author=FollowViewsTests.user
        )
        response = self.authorized_client.get(reverse('posts:follow_index'))
        post_context = response.context.get('page_obj')
        self.assertIn(post, post_context)

    def test_new_post_on_no_folowers_lent(self):
        """Новая запись пользователя не появляется в ленте тех,
        кто не подписан."""
        post = Post.objects.create(
            author=FollowViewsTests.user,
            text='new post  for test follow',
        )
        self.new_user = User.objects.create_user(username='NewHasNoName')
        self.new_authorized_client = Client()
        self.new_authorized_client.force_login(self.new_user)
        Follow.objects.create(
            user=self.new_user,
            author=self.user
        )
        response = self.new_authorized_client.get(
            reverse('posts:follow_index')
        )
        post_context = response.context.get('page_obj')
        self.assertNotIn(post, post_context)

    def test_profile_follow_view(self):
        """При подписке происходит redirect на профайл автора"""
        author = FollowViewsTests.user
        response = self.authorized_client.get(
            reverse('posts:profile_follow', args=(author,))
        )
        self.assertRedirects(
            response, reverse('posts:profile', args=(author.username,))
        )

    def test_profile_unfollow_view(self):
        """При подписке происходит redirect на профайл автора"""
        author = FollowViewsTests.user
        Follow.objects.create(
            user=self.user,
            author=author
        )
        response = self.authorized_client.get(
            reverse('posts:profile_unfollow', args=(author,))
        )
        self.assertRedirects(
            response, reverse('posts:profile', args=(author.username,))
        )


class PaginatorViewsTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='auth')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='Test-slug',
            description='Тестовое описание',
        )
        posts = [
            Post(
                text=f'Text post #{i}',
                author=cls.user,
                group=cls.group,
            ) for i in range(0, 27)
        ]
        Post.objects.bulk_create(posts)

    def setUp(self):
        self.author = PaginatorViewsTests.user
        self.authorized_client_author = Client()
        self.authorized_client_author.force_login(self.author)

    def test_posts_paginator(self):
        """Тест paginator на страницах с постами."""
        post_count = Post.objects.count()
        pages_count = post_count // settings.POST_IN_PAGE + 1
        posts_count_on_last_page = post_count % settings.POST_IN_PAGE
        index_url = ('posts:index', None)
        profile_url = (
            'posts:profile', (PaginatorViewsTests.user.username,)
        )
        group_url = (
            'posts:group_list', (PaginatorViewsTests.group.slug,)
        )
        paginator_urls = (
            index_url,
            profile_url,
            group_url,
        )
        pages = {}
        for page_num in range(1, pages_count):
            pages[page_num] = settings.POST_IN_PAGE
        pages[pages_count] = posts_count_on_last_page

        for name, args in paginator_urls:
            for page, amnt in pages.items():
                with self.subTest(name=name, page=page):
                    response = self.authorized_client_author.get(
                        reverse(name, args=args), {'page': page}
                    )
                    self.assertEqual(
                        len(response.context.get('page_obj').object_list), amnt
                    )
