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
