from django.contrib import admin
from form_designer.models import FormDefinition, FormDefinitionField, FormDefinitionFieldChoice, FormSubmission, FormFieldSubmission
from django import forms
from django.utils.translation import ugettext as _
from django.db import models
from django.conf import settings
import os

MEDIA_SUBDIR = 'form_designer'


#==============================================================================
class FormDefinitionFieldInlineForm(forms.ModelForm):
    
    #--------------------------------------------------------------------------
    class Meta:
        model = FormDefinitionField
        
        
    #--------------------------------------------------------------------------
    def clean_choice_model(self):
        if not self.cleaned_data['choice_model'] and self.cleaned_data.has_key('field_class') and self.cleaned_data['field_class'] in ('forms.ModelChoiceField', 'forms.ModelMultipleChoiceField'):
            raise forms.ValidationError(_('This field class requires a model.'))
        return self.cleaned_data['choice_model']



#==============================================================================
class FormDefinitionFieldInline(admin.StackedInline):
    form = FormDefinitionFieldInlineForm
    model = FormDefinitionField
    extra = 8
    fieldsets = [
        (_('Basic'), {'fields': ['name', 'field_class', 'required', 'initial']}),
        (_('Display'), {'fields': ['label', 'widget', 'help_text', 'position', 'include_result']}),
        (_('Text'), {'fields': ['max_length', 'min_length']}),
        (_('Numbers'), {'fields': ['max_value', 'min_value', 'max_digits', 'decimal_places']}),
        (_('Regex'), {'fields': ['regex']}),
        (_('Choices'), {'fields': ['choices']}),
        (_('Model Choices'), {'fields': ['choice_model', 'choice_model_empty_label']}),
    ]



#==============================================================================
class FormDefinitionForm(forms.ModelForm):
    
    #--------------------------------------------------------------------------
    class Meta:
        model = FormDefinition
        
        
    #--------------------------------------------------------------------------
    class Media:
        js = ([
                # Use central jQuery
                settings.JQUERY_JS,
                # and use jQuery UI bundled with this app
                os.path.join(MEDIA_SUBDIR, 'lib/jquery/ui.core.js'),
                os.path.join(MEDIA_SUBDIR, 'lib/jquery/ui.sortable.js'),
            ] if hasattr(settings, 'JQUERY_JS') else [
                # Use jQuery bundled with CMS
                os.path.join(settings.CMS_MEDIA_URL, 'js/lib/jquery.js'),
                os.path.join(settings.CMS_MEDIA_URL, 'js/lib/ui.core.js'),
                os.path.join(settings.CMS_MEDIA_URL, 'js/lib/ui.sortable.js'),
            ] if hasattr(settings, 'CMS_MEDIA_URL') else [
                # or use jQuery bundled with this app
                os.path.join(MEDIA_SUBDIR, 'lib/jquery/jquery.js'),
                os.path.join(MEDIA_SUBDIR, 'lib/jquery/ui.core.js'),
                os.path.join(MEDIA_SUBDIR, 'lib/jquery/ui.sortable.js'),
            ])+[os.path.join(MEDIA_SUBDIR, 'js/lib/django-admin-tweaks-js-lib/js', basename) for basename in (
                'jquery-inline-positioning.js',
                'jquery-inline-rename.js',
                'jquery-inline-collapsible.js',
                'jquery-inline-fieldset-collapsible.js',
                'jquery-inline-prepopulate-label.js',
            )]



#==============================================================================
class FormDefinitionAdmin(admin.ModelAdmin):
    fieldsets = [
        (_('Basic'), {'fields': ['name', 'method', 'action', 'title', 'allow_get_initial', 'log_data', 'success_redirect', 'success_clear']}),
        (_('Mail form'), {'fields': ['mail_to', 'mail_from', 'mail_subject'], 'classes': ['collapse']}),
        (_('Templates'), {'fields': ['message_template', 'form_template_name'], 'classes': ['collapse']}),
        (_('Messages'), {'fields': ['success_message', 'error_message', 'submit_label'], 'classes': ['collapse']}),
    ]
    list_display = ('name', 'title', 'method', 'count_fields')
    form = FormDefinitionForm
    inlines = [
        FormDefinitionFieldInline,
    ]



#==============================================================================
class FormFieldSubmissionInline(admin.StackedInline):
    model = FormFieldSubmission
    extra = 0



#==============================================================================
class FormSubmissionAdmin(admin.ModelAdmin):
    list_display = ('form_title', 'form_name', 'created')
    inlines = [
        FormFieldSubmissionInline,
    ]
    
    
    #--------------------------------------------------------------------------
    def form_title(self, obj):
        return u'%s' % obj.form_definition.title if obj.form_definition else _('No fields attached')
    form_title.short_description = _('Form title')
            

    #--------------------------------------------------------------------------
    def form_name(self, obj):
        return u'%s' % obj.form_definition.name if obj.form_definition else _('No fields attached')
    form_name.short_description = _('Form name')
    


admin.site.register(FormDefinition, FormDefinitionAdmin)
admin.site.register(FormDefinitionFieldChoice)
admin.site.register(FormSubmission, FormSubmissionAdmin)
admin.site.register(FormFieldSubmission)

