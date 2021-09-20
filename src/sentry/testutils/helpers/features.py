__all__ = ["Feature", "with_feature"]

import collections
import logging
from contextlib import contextmanager

import sentry.features
from sentry.utils.compat.mock import patch

logger = logging.getLogger(__name__)


@contextmanager
def Feature(names):
    """
    Control whether a feature is enabled.

    A single feature may be conveniently enabled with

    >>> with Feature('feature-1'):
    >>>   # Executes with feature-1 enabled

    More advanced enabling / disabling can be done using a dict

    >>> with Feature({'feature-1': True, 'feature-2': False}):
    >>>   # Executes with feature-1 enabled and feature-2 disabled

    The following two invocations are equivalent:

    >>> with Feature(['feature-1', 'feature-2']):
    >>>   # execute with both features enabled
    >>> with Feature({'feature-1': True, 'feature-2': True}):
    >>>   # execute with both features enabled
    """
    if isinstance(names, str):
        names = {names: True}

    elif not isinstance(names, collections.Mapping):
        names = {k: True for k in names}

    default_features = sentry.features.has

    def features_override(name, *args, **kwargs):
        if name in names:
            return names[name]
        else:
            default_value = default_features(name, *args, **kwargs)
            if default_value:
                logger.info("Flag %s defaulting to %s", repr(name), default_value)
            return default_value

    with patch("sentry.features.has") as features_has:
        features_has.side_effect = features_override
        yield


def with_feature(feature):
    def decorator(func):
        def wrapped(self, *args, **kwargs):
            with Feature(feature):
                return func(self, *args, **kwargs)

        return wrapped

    return decorator
