import warnings
from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django_scopes import ScopedManager
from i18nfield.fields import I18nTextField
from pretix.base.models import Question


class QuestionPlaceholder(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        verbose_name=_("Question"),
        related_name="plugin_question_placeholders",
    )
    slug = models.SlugField(
        null=True,
        blank=True,
        verbose_name=_("Placeholder name"),
        help_text=_(
            "By default, the placeholder will look like {question_123}, but you can change it to {question_something_else}"
        ),
    )
    fallback_content = I18nTextField(
        null=True,
        blank=True,
        verbose_name=_("Fallback"),
        help_text=_("Will be used when no other condition matches. Can be empty."),
    )
    use_fallback_when_unanswered = models.BooleanField(
        default=False,
        verbose_name=_("Use fallback when the question was not answered"),
        help_text=_(
            "Turn on if you always want to use the fallback. Otherwise, the placeholder will be ignored when the user has not answered the question."
        ),
    )

    objects = ScopedManager(organizer="question__event__organizer")

    @property
    def placeholder_name(self):
        return self.slug or self.question_id

    def render(self, order):
        from pretix.base.models.orders import QuestionAnswer

        answers = QuestionAnswer.objects.filter(
            orderposition__order=order, question=self.question
        )
        if not answers:
            if self.use_fallback_when_unanswered:
                return self.fallback_content
            return

        if len(answers) > 1:
            warnings.warn(
                f"Cannot render email placeholders for multiple answers for {order.code}"
            )
            return

        answer = answers[0]
        for rule in self.rules.all():
            if rule.matches(answer):
                return rule.content
        if self.use_fallback_when_unanswered:
            return self.fallback_content
        return ""


class PlaceholderRule(models.Model):
    class ComparisonOperation(models.TextChoices):
        EQUALS = "eq", _("Equals")
        IEQUALS = "ieq", _("Equals (case insensitive)")
        LESS_THAN = "lt", _("Less than / earlier than")
        LESS_OR_EQUAL_THAN = "lte", _("Less or same as / earlier or same as")
        MORE_THAN = "gt", _("Greater than / later than")
        MORE_OR_EQUAL_THAN = "gte", _("Greater or same as / later or same as")
        IS_TRUE = "bool", _("Is true / has been answered")

    placeholder = models.ForeignKey(
        QuestionPlaceholder, on_delete=models.CASCADE, related_name="rules"
    )

    content = I18nTextField(
        null=True,
        blank=True,
        verbose_name=_("Content"),
        help_text=_("Will be inserted into the email if the condition matches."),
    )
    condition_content = models.TextField()
    condition_operation = models.CharField(
        max_length=4, choices=ComparisonOperation.choices
    )
    position = models.IntegerField(default=0)

    class Meta:
        ordering = ("position", "id")

    @cached_property
    def question_type(self):
        return self.placeholder.question.type

    @cached_property
    def value(self):
        return self.placeholder.question.clean_answer(self.condition_content)

    @cached_property
    def allowed_methods(self):
        global_methods = [self.ComparisonOperation.IS_TRUE]

        comparison_methods = global_methods + [
            self.ComparisonOperation.EQUALS,
            self.ComparisonOperation.LESS_THAN,
            self.ComparisonOperation.LESS_OR_EQUAL_THAN,
            self.ComparisonOperation.MORE_THAN,
            self.ComparisonOperation.MORE_OR_EQUAL_THAN,
        ]

        text_methods = [self.ComparisonOperation.IEQUALS]

        methods = {
            Question.TYPE_BOOLEAN: global_methods + [self.ComparisonOperation.EQUALS],
            Question.TYPE_FILE: global_methods,
            Question.TYPE_DATE: comparison_methods,
            Question.TYPE_DATETIME: comparison_methods,
            Question.TYPE_TIME: comparison_methods,
            Question.TYPE_NUMBER: comparison_methods,
            Question.TYPE_PHONENUMBER: comparison_methods,
            Question.TYPE_STRING: comparison_methods + text_methods,
            Question.TYPE_TEXT: comparison_methods + text_methods,
            Question.TYPE_COUNTRYCODE: comparison_methods,
            Question.TYPE_CHOICE: comparison_methods,
            Question.TYPE_CHOICE_MULTIPLE: comparison_methods,
        }
        return set(methods[self.question_type])

    @cached_property
    def comparison_method(self):
        methods = {
            self.ComparisonOperation.EQUALS: self._compare_equals,
            self.ComparisonOperation.IEQUALS: self._compare_iequals,
            self.ComparisonOperation.LESS_THAN: self._compare_less_than,
            self.ComparisonOperation.LESS_OR_EQUAL_THAN: self._compare_less_or_equal_than,
            self.ComparisonOperation.MORE_THAN: self._compare_more_than,
            self.ComparisonOperation.MORE_OR_EQUAL_THAN: self._compare_more_or_equal_than,
            self.ComparisonOperation.IS_TRUE: self._compare_boolean,
        }
        return methods[self.comparison_operation]

    def _compare_boolean(self, value):
        return bool(value)

    def _compare_equals(self, value):
        return value == self.value

    def _compare_iequals(self, value):
        return str(value).lower() == str(self.value).lower()

    def _compare_less_than(self, value):
        return value < self.value

    def _compare_less_or_equal_than(self, value):
        return value <= self.value

    def _compare_more_than(self, value):
        return value > self.value

    def _compare_more_or_equal_than(self, value):
        return value >= self.value

    def matches(self, answer):
        if self.comparison_method not in self.allowed_methods:
            warnings.warn(f"Forbidden comparison method {self.comparison_method}.")
            return False

        try:
            answer_value = answer.question.clean(answer.answer)
        except Exception as e:
            warnings.warn(f"Error parsing answer value: {e}")
            return False

        try:
            return bool(self.comparison_method(answer_value))
        except Exception as e:
            warnings.warn(
                f"Error when comparing values {self.value} and {answer_value}: {e}"
            )
