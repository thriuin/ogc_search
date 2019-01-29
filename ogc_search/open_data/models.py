from django.db import models

# Create your models here.


class Organization(models.Model):
    acronym = models.CharField(max_length=32)
    orgname_en = models.CharField(max_length=150)
    orgname_fr = models.CharField(max_length=150)

    def __str__(self):
        return  "{}".format(self.acronym)

    def __unicode__(self):
        return "{}".format(self.id)



class CatalogType(models.Model):
    code = models.CharField(max_length=32)
    colname_en = models.CharField(max_length=150)
    colname_fr = models.CharField(max_length=150)

    def __str__(self):
        return  "{}".format(self.code)

    def __unicode__(self):
        return "{}".format(self.id)


class Collections(models.Model):
    code = models.CharField(max_length=32)
    colname_en = models.CharField(max_length=150)
    colname_fr = models.CharField(max_length=150)

    def __str__(self):
        return  "{}".format(self.code)

    def __unicode__(self):
        return "{}".format(self.id)


class QueryLog(models.Model):
    language = models.CharField(max_length=2)
    action = models.CharField(max_length=12)
    timestamp = models.TimeField()
    search_terms = models.CharField(max_length=150)
    organization_terms = models.CharField(max_length=256)
    portal_terms = models.CharField(max_length=128)
    jurisdiction_terms = models.CharField(max_length=128)
    collection_terms = models.CharField(max_length=256)
    keyword_terms = models.CharField(max_length=256)
    subject_terms = models.CharField(max_length=256)
    format_terms = models.CharField(max_length=256)
    res_type_terms = models.CharField(max_length=256)
    frequency_terms = models.CharField(max_length=256)
