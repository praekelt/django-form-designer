from django.db import models
from django.utils.translation import ugettext, ugettext_lazy as _
from django.forms import widgets
from django.core.mail import send_mail
from django.conf import settings
from form_designer import app_settings
import re
from form_designer.pickled_object_field import PickledObjectField
from form_designer.model_name_field import ModelNameField
from form_designer.template_field import TemplateTextField, TemplateCharField


#==============================================================================
class FormDefinition(models.Model):
    """
    A model that defines a form and its components and properties.
    """
    
    name = models.SlugField(_('Name'), max_length=255, unique=True)
    title = models.CharField(_('Title'), max_length=255, blank=True, null=True)
    action = models.URLField(_('Target URL'), help_text=_('If you leave this empty, the page where the form resides will be requested, and you can use the mail form and logging features. You can also send data to external sites: For instance, enter "http://www.google.ch/search" to create a search form.'), max_length=255, blank=True, null=True)
    mail_to = TemplateCharField(_('Send form data to e-mail address'), help_text=('Separate several addresses with a comma. Your form fields are available as template context. Example: "admin@domain.com, {{ from_email }}" if you have a field named `from_email`.'), max_length=255, blank=True, null=True)
    mail_from = TemplateCharField(_('Sender address'), max_length=255, help_text=('Your form fields are available as template context. Example: "{{ firstname }} {{ lastname }} <{{ from_email }}>" if you have fields named `first_name`, `last_name`, `from_email`.'), blank=True, null=True)
    mail_subject = TemplateCharField(_('e-Mail subject'), max_length=255, help_text=('Your form fields are available as template context. Example: "Contact form {{ subject }}" if you have a field named `subject`.'), blank=True, null=True)
    method = models.CharField(_('Method'), max_length=10, default="POST", choices = (('POST', 'POST'), ('GET', 'GET')))
    success_message = models.CharField(_('Success message'), max_length=255, blank=True, null=True)
    error_message = models.CharField(_('Error message'), max_length=255, blank=True, null=True)
    submit_label = models.CharField(_('Submit button label'), max_length=255, blank=True, null=True)
    log_data = models.BooleanField(_('Log form data'), help_text=_('Logs all form submissions to the database.'), default=True)
    success_redirect = models.BooleanField(_('Redirect after success'), help_text=_('You should install django_notify if you want to enable this.') if not 'django_notify' in settings.INSTALLED_APPS else None, default=False)
    success_clear = models.BooleanField(_('Clear form after success'), default=True)
    allow_get_initial = models.BooleanField(_('Allow initial values via URL'), help_text=_('If enabled, you can fill in form fields by adding them to the query string.'), default=True)
    message_template = TemplateTextField(_('Message template'), help_text=_('Your form fields are available as template context. Example: "{{ message }}" if you have a field named `message`. To iterate over all fields, use the variable `data` (a list containing a dictionary for each form field, each containing the elements `name`, `label`, `value`).'), blank=True, null=True)
    form_template_name = models.CharField(_('Form template'), max_length=255, choices=app_settings.get('FORM_DESIGNER_FORM_TEMPLATES'), blank=True, null=True)


    #--------------------------------------------------------------------------
    class Meta:
        verbose_name = _('form')
        verbose_name_plural = _('forms')


    #--------------------------------------------------------------------------
    def get_field_dict(self):
        dict = {}
        for field in self.fields.all():
            dict[field.name] = field
        return dict
        
        
    #--------------------------------------------------------------------------
    def get_form_data(self, form):
        data = []
        field_dict = self.get_field_dict()
        form_keys = form.fields.keys()
        def_keys = field_dict.keys()
        for key in form_keys:
            if key in def_keys and field_dict[key].include_result:
                value = form.cleaned_data[key]
                if getattr(value, '__form_data__', False):
                    value = value.__form_data__()
                data.append({'name': key, 'label': form.fields[key].label, 'value': value})
        return data
        
        
    #--------------------------------------------------------------------------
    def get_form_data_dict(self, form_data):
        dict = {}
        for field in form_data:
            dict[field['name']] = field['value']
        return dict


    #--------------------------------------------------------------------------
    def compile_message(self, form_data, template=None):
        from django.template.loader import get_template
        from django.template import Context, Template
        if template:
            t = get_template(template)
        elif not self.message_template:
            t = get_template('txt/formdefinition/data_message.txt')
        else:
            t = Template(self.message_template)
        context = Context(self.get_form_data_dict(form_data))
        context['data'] = form_data
        return t.render(context)


    #--------------------------------------------------------------------------
    def count_fields(self):
        return self.fields.count()
    count_fields.short_description = _('Fields')


    #--------------------------------------------------------------------------
    def __unicode__(self):
        return self.title or self.name
        
    
    #--------------------------------------------------------------------------
    def log(self, form):
        """
        Saves the form submission.
        """
        
        form_data = self.get_form_data(form)
        field_dict = self.get_field_dict()
        
        # create a submission
        submission = FormSubmission()
        submission.save()
        
        # log each field's value individually
        for field_data in form_data:
            field_submission = FormFieldSubmission(submission=submission, definition_field=field_dict[field_data['name']],
                value=field_data['value'])
            field_submission.save()


    #--------------------------------------------------------------------------
    def string_template_replace(self, text, context_dict):
        from django.template import Context, Template, TemplateSyntaxError
        try:
            t = Template(text)
            return t.render(Context(context_dict))
        except TemplateSyntaxError:
            return text


    #--------------------------------------------------------------------------
    def send_mail(self, form):
        form_data = self.get_form_data(form)
        message = self.compile_message(form_data)
        context_dict = self.get_form_data_dict(form_data)

        import re 
        mail_to = re.compile('\s*[,;]+\s*').split(self.mail_to)
        for key, email in enumerate(mail_to):
            mail_to[key] = self.string_template_replace(email, context_dict)
        
        mail_from = self.mail_from or None
        if mail_from:
            mail_from = self.string_template_replace(mail_from, context_dict)
        
        if self.mail_subject:
            mail_subject = self.string_template_replace(self.mail_subject, context_dict)
        else:
            mail_subject = self.title
        
        import logging
        logging.debug('Mail: '+repr(mail_from)+' --> '+repr(mail_to));
        
        from django.core.mail import send_mail
        send_mail(mail_subject, message, mail_from or None, mail_to, fail_silently=False)


    #--------------------------------------------------------------------------
    @property
    def submit_flag_name(self):
        name = app_settings.get('FORM_DESIGNER_SUBMIT_FLAG_NAME') % self.name
        while self.fields.filter(name__exact=name).count() > 0:
            name += '_'
        return name
        
        
    
    #--------------------------------------------------------------------------
    def to_field_list(self):
        """
        Converts this form definition into a list of dictionaries, each
        dictionary representing a field and its components.
        
        @param fields A list of fields to include. By default, if this is
            None, all fields will be generated.
        @param field_name_replacements
        """
        
        field_arr = []
        
        # run through all of the fields associated with this definition
        for field in self.fields.all():
            choices = []
            if field.choices.count():
                choices = [{'value': u'%s' % choice.value, 'label': u'%s' % choice.label} for choice in field.choices.all()]
            elif field.choice_model:
                choices = [{'value': u'%s' % obj.id, 'label': u'%s' % obj} for obj in ModelNameField.get_model_from_string(field.choice_model).objects.all()]
            
            field_item = {
                'name': u'%s' % field.name,
                'label': u'%s' % field.label,
                'class': u'%s' % field.field_class,
                'position': u'%s' % field.position,
                'widget': u'%s' % field.widget,
                'initial': u'%s' % field.initial,
                'help_text': u'%s' % field.help_text,
            }
            if choices:
                field_item['choices'] = choices



#==============================================================================
class FormDefinitionFieldChoice(models.Model):
    """
    A single choice available for a form definition field.
    """
    
    label = models.TextField(_('Label'), help_text=_('A descriptive value for the choice'), blank=True, null=True)
    value = models.TextField(_('Value'), help_text=_('The value of the choice when submitting the form'), blank=True, null=True)
    
    
    #--------------------------------------------------------------------------
    def __unicode__(self):
        return u'%s (%s)' % (self.label, self.value)



#==============================================================================
class FormDefinitionField(models.Model):
    """
    A single field within a form definition.
    """

    form_definition = models.ForeignKey(FormDefinition, verbose_name=_('Form definition'), related_name='fields')
    field_class = models.CharField(_('Field class'), choices=app_settings.get('FORM_DESIGNER_FIELD_CLASSES'), max_length=32)
    position = models.IntegerField(_('Position'), blank=True, null=True)

    name = models.SlugField(_('Name'), max_length=255)
    label = models.CharField(_('Label'), max_length=255, blank=True, null=True)
    required = models.BooleanField(_('Required'), default=True)
    include_result = models.BooleanField(_('Include in result'), help_text=('If this is disabled, the field value will not be included in logs and e-mails generated from form data.'), default=True)
    widget = models.CharField(_('Widget'), default='', choices=app_settings.get('FORM_DESIGNER_WIDGET_CLASSES'), max_length=255, blank=True, null=True)
    initial = models.TextField(_('Initial value'), blank=True, null=True)
    help_text = models.CharField(_('Help text'), max_length=255, blank=True, null=True)
    
    # the new model
    choices = models.ManyToManyField(FormDefinitionFieldChoice, verbose_name=_('Choices'), help_text=_('The various options from which the user can choose'), blank=True, null=True)

    max_length = models.IntegerField(_('Max. length'), blank=True, null=True)
    min_length = models.IntegerField(_('Min. length'), blank=True, null=True)
    max_value = models.FloatField(_('Max. value'), blank=True, null=True)
    min_value = models.FloatField(_('Min. value'), blank=True, null=True)
    max_digits = models.IntegerField(_('Max. digits'), blank=True, null=True)
    decimal_places = models.IntegerField(_('Decimal places'), blank=True, null=True)

    regex = models.CharField(_('Regular Expression'), max_length=255, blank=True, null=True)

    choice_model_choices = app_settings.get('FORM_DESIGNER_CHOICE_MODEL_CHOICES')
    choice_model = ModelNameField(_('Data model'), max_length=255, blank=True, null=True, choices=choice_model_choices, help_text=_('your_app.models.ModelName' if not choice_model_choices else None))
    choice_model_empty_label = models.CharField(_('Empty label'), max_length=255, blank=True, null=True)

    
    #--------------------------------------------------------------------------
    def save(self, *args, **kwargs):
        if self.position == None:
            self.position = 0
        super(FormDefinitionField, self).save()


    #--------------------------------------------------------------------------
    def ____init__(self, field_class=None, name=None, required=None, widget=None, label=None, initial=None, help_text=None, *args, **kwargs):
        super(FormDefinitionField, self).__init__(*args, **kwargs)
        self.name = name
        self.field_class = field_class
        self.required = required
        self.widget = widget
        self.label = label
        self.initial = initial
        self.help_text = help_text


    #--------------------------------------------------------------------------
    def get_form_field_init_args(self):
        args = {
            'required': self.required,
            'label': self.label if self.label else '',
            'initial': self.initial if self.initial else None,
            'help_text': self.help_text,
        }
        
        if self.field_class in ('forms.CharField', 'forms.EmailField', 'forms.RegexField'):
            args.update({
                'max_length': self.max_length,
                'min_length': self.min_length,
            })

        if self.field_class in ('forms.IntegerField', 'forms.DecimalField'):
            args.update({
                'max_value': int(self.max_value) if self.max_value != None else None,
                'min_value': int(self.min_value) if self.min_value != None else None,
            })

        if self.field_class == 'forms.DecimalField':
            args.update({
                'max_value': self.max_value,
                'min_value': self.min_value,
                'max_digits': self.max_digits,
                'decimal_places': self.decimal_places,
            })

        if self.field_class == 'forms.RegexField':
            if self.regex:
                args.update({
                    'regex': self.regex
                })

        if self.field_class in ('forms.ChoiceField', 'forms.MultipleChoiceField'):
            print "Choices count:", self.choices.count()
            if self.choices.count():
                # new method of creating choices
                choices = [(choice.value, choice.label) for choice in self.choices.all()]
                args.update({
                    'choices': tuple(choices)
                })
                
                print "Choices:", choices

        if self.field_class in ('forms.ModelChoiceField', 'forms.ModelMultipleChoiceField'):
            args.update({
                'queryset': ModelNameField.get_model_from_string(self.choice_model).objects.all()
            })
        
        if self.field_class == 'forms.ModelChoiceField':
            args.update({
                'empty_label': self.choice_model_empty_label
            })

        if self.widget:
            args.update({
                'widget': eval(self.widget)()
            })
        
        return args


    #--------------------------------------------------------------------------
    class Meta:
        verbose_name = _('field')
        verbose_name_plural = _('fields')
        ordering = ['position']

    #--------------------------------------------------------------------------
    def __unicode__(self):
        return self.label if self.label else self.name



#==============================================================================
class FormSubmission(models.Model):
    """
    Represents a single submission of a particular type of form definition.
    """
    
    created = models.DateTimeField(_('Created'), auto_now=True)
    
    #--------------------------------------------------------------------------
    class Meta:
        verbose_name = _('form submission')
        verbose_name_plural = _('form submissions')
        ordering = ['-created']
        
    
    #--------------------------------------------------------------------------
    def __unicode__(self):
        form_definition = self.form_definition
        # if this submission has fields attached to it
        if form_definition:
            return u'%s at %s' % (form_definition, self.created)
        else:
            return u'Empty submission at %s' % self.created
        
        
    
    #--------------------------------------------------------------------------
    @property
    def form_definition(self):
        return self.fields.all()[0].definition_field.form_definition if self.fields.count() else None



#==============================================================================
class FormFieldSubmission(models.Model):
    """
    Represents the content of a single submission's field.
    """
    
    submission = models.ForeignKey(FormSubmission, verbose_name=_('Form submission'), help_text=_('The submission to which this particular submission component belongs'),
        related_name='fields')
    definition_field = models.ForeignKey(FormDefinitionField, verbose_name=_('Form definition field'),
        help_text=_('The field in the form definition to which this submitted value belongs'),
        related_name='submissions')
    value = models.TextField(_('Value'), help_text=_('The actual submitted value'))
    
    
    #--------------------------------------------------------------------------
    def __unicode__(self):
        value = u'%s' % self.value
        truncated_value = value if len(value) < 10 else value[:10]+'...'
        return u'%s: %s (%s)' % (self.definition_field, u'%s=%s' % (truncated_value, self.choice_label) if self.choice_label else truncated_value, self.submission)
        
    
    #--------------------------------------------------------------------------
    @property
    def choice_label(self):
        """
        Retrieves the label of the choice made by the user, should this
        submission's field be linked to a set of choices.
        
        TODO: Account for model choice fields.
        """
        
        try:
            # get the first choice that matches the available ones
            choice = self.definition_field.choices.filter(value=self.value)[0]
        except:
            return None
        
        return u'%s' % choice.label




#==============================================================================
if 'cms' in settings.INSTALLED_APPS:
    from cms.models import CMSPlugin

    class CMSFormDefinition(CMSPlugin):
        form_definition = models.ForeignKey(FormDefinition, verbose_name=_('Form'))

        def __unicode__(self):
            return self.form_definition.__unicode__()
