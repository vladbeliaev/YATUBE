import shutil
import tempfile
from http import HTTPStatus

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ..models import Group, Post

User = get_user_model()
TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostCreateFormTests(TestCase):
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

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.guest_client = Client()
        self.user = User.objects.create_user(username='HasNoName')
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        self.author = PostCreateFormTests.user
        self.authorized_client_author = Client()
        self.authorized_client_author.force_login(self.author)

    def test_form_create(self):
        post_count = Post.objects.count()
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
        form_data = {
            'group': self.group.id,
            'text': 'text new post',
            'image': uploaded,
        }
        response = self.authorized_client.post(
            reverse('posts:post_create'), data=form_data, follow=True
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertRedirects(response, reverse(
            'posts:profile', kwargs={'username': self.user.username}
        ))
        post_count_after_create = Post.objects.count()
        self.assertEqual(post_count_after_create, post_count + 1)
        new_post = Post.objects.all().first()
        self.assertEqual(new_post.text, form_data['text'])
        self.assertEqual(new_post.group.id, form_data['group'])
        self.assertEqual(new_post.author, self.user)
        expected_image_name = f"posts/{form_data['image'].name}"
        self.assertEqual(new_post.image.name, expected_image_name)

    def test_form_update(self):
        post_count = Post.objects.count()
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        uploaded = SimpleUploadedFile(
            name='small2.gif',
            content=small_gif,
            content_type='image/gif',
        )
        form_data = {
            'group': self.group.id,
            'text': 'text update post',
            'image': uploaded,
        }
        post_id = PostCreateFormTests.post.pk
        response = self.authorized_client_author.post(
            reverse('posts:post_edit', args=(post_id,)),
            data=form_data,
        )
        self.assertRedirects(
            response,
            reverse('posts:post_detail', args=(post_id,))
        )
        update_post = Post.objects.get(pk=post_id)
        post_count_after_update = Post.objects.count()
        self.assertEqual(post_count_after_update, post_count)
        self.assertEqual(
            update_post.text, form_data['text']
        )
        self.assertEqual(
            update_post.group.id, form_data['group']
        )
        self.assertEqual(
            update_post.author, self.author
        )
        image_name = form_data['image'].name
        expected_image_name = f'posts/{image_name}'
        self.assertEqual(update_post.image.name, expected_image_name)

    def test_form_dont_create_by_guest_client(self):
        post_count = Post.objects.count()
        form_data = {
            'group': self.group.id,
            'text': 'text new post',
        }
        response = self.guest_client.post(
            reverse('posts:post_create'), data=form_data, follow=True
        )
        next = '?next='
        self.assertRedirects(
            response,
            reverse('users:login') + next + reverse('posts:post_create')
        )
        post_count_after_response = Post.objects.count()
        self.assertEqual(post_count, post_count_after_response)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class CommentCreateFormTests(TestCase):
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

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.guest_client = Client()
        self.user = User.objects.create_user(username='HasNoName')
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        self.author = CommentCreateFormTests.user
        self.authorized_client_author = Client()
        self.authorized_client_author.force_login(self.author)

    def test_comment_dont_add_by_guest_client(self):
        post = CommentCreateFormTests.post
        count_comments = post.comments.count()
        form_data = {
            'text': 'text new comment',
        }
        response = self.guest_client.post(
            reverse('posts:add_comment', args=(post.pk,)),
            data=form_data,
            follow=True
        )
        next = '?next='
        self.assertRedirects(
            response,
            reverse('users:login') + next + reverse(
                'posts:add_comment', args=(post.pk,)
            )
        )
        count_comments_after_add = post.comments.count()
        self.assertEqual(count_comments, count_comments_after_add)

    def test_comment_add_by_authorized_client(self):
        post = CommentCreateFormTests.post
        count_comments = post.comments.count()
        form_data = {
            'text': 'text new comment',
        }
        self.authorized_client.post(
            reverse('posts:add_comment', args=(post.pk,)),
            data=form_data,
            follow=True
        )
        count_comments_after_add = post.comments.count()
        self.assertEqual(count_comments + 1, count_comments_after_add)
        last_comment_on_post = post.comments.first()
        self.assertEqual(last_comment_on_post.text, form_data['text'])
        self.assertEqual(last_comment_on_post.author, self.user)
