from django.db import models

from sentry.db.models import FlexibleForeignKey

from . import AvatarBase


class SentryAppAvatar(AvatarBase):
    """
    A SentryAppAvatar associates a SentryApp with a logo photo File
    and specifies which type of logo it is.
    """

    AVATAR_TYPES = ((0, "letter_avatar"), (1, "upload"))

    FILE_TYPE = "avatar.file"

    sentry_app = FlexibleForeignKey("sentry.SentryApp", unique=True, related_name="avatar")
    avatar_type = models.PositiveSmallIntegerField(default=0, choices=AVATAR_TYPES)
    color = models.BooleanField(default=False)
    # e.g. issue linking logos will not have color

    class Meta:
        app_label = "sentry"
        db_table = "sentry_sentryappavatar"

    def get_cache_key(self, size):
        return f"sentry_app_avatar:{self.sentry_app_id}:{size}"
