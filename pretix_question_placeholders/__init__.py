from django.utils.translation import gettext_lazy

try:
    from pretix.base.plugins import PluginConfig
except ImportError:
    raise RuntimeError("Please use pretix 2.7 or above to run this plugin!")

__version__ = "0.7.0"


class PluginApp(PluginConfig):
    name = "pretix_question_placeholders"
    verbose_name = "Email content based on question answers"

    class PretixPluginMeta:
        name = gettext_lazy("Email content based on question answers")
        author = "Tobias Kunze"
        description = gettext_lazy(
            "Add content to your emails based on the questions the customer answered, and the answer they gave."
        )
        visible = True
        version = __version__
        category = "CUSTOMIZATION"
        compatibility = "pretix>=2.7.0"

    def ready(self):
        from . import signals  # NOQA


default_app_config = "pretix_question_placeholders.PluginApp"
