from django.db import models
from django.utils.timezone import now

# Create your models here.

class ATI(models.Model):
    org_shortform_en = models.CharField(max_length=32, blank=True)
    org_shortform_fr = models.CharField(max_length=32, blank=True)
    organization_en = models.CharField(max_length=150, blank=True)
    organization_fr = models.CharField(max_length=150, blank=True)
    month_name_en = models.CharField(max_length=32, blank=True)
    month_name_fr = models.CharField(max_length=32, blank=True)
    year = models.CharField(max_length=4, blank=True)
    month = models.CharField(max_length=4, blank=True, help_text="Enter number 1 to 12")
    request_summary_en = models.TextField(blank=True, null=True)
    request_summary_fr = models.TextField(blank=True, null=True)
    request_number = models.CharField(max_length=150, blank=True)
    number_of_pages = models.CharField(max_length=6, blank=True)
    disposition_en = models.CharField(max_length=32, blank=True)
    disposition_fr = models.CharField(max_length=32, blank=True)
    id = models.CharField(max_length=32, verbose_name="Identifier", primary_key=True)

    def __str__(self):
        return "{}".format(self.id)

    def __unicode__(self):
        return "{}".format(self.id)

    def save(self, *args, **kwargs):
        super(ATI, self).save(*args, **kwargs)


class Department(models.Model):
    acronym = models.CharField(max_length=32)
    orgname_en = models.CharField(max_length=150)
    orgname_fr = models.CharField(max_length=150)

    def __str__(self):
        return  "{}".format(self.acronym)
