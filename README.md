# ogc_search
Django based search for the Canadian Open Government Portal 

This project uses a Django framework web application as a thin frontend to Solr to do searching of datasets and 
proactive disclosure data for the Open Government Portal. Instead of using the usual CKAN Solr 6 cores, data is 
loaded into custom Solr cores that better support Canada's two official languages.

[![Total alerts](https://img.shields.io/lgtm/alerts/g/thriuin/ogc_search.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/thriuin/ogc_search/alerts/)
[![Language grade: JavaScript](https://img.shields.io/lgtm/grade/javascript/g/thriuin/ogc_search.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/thriuin/ogc_search/context:javascript)
[![Language grade: JavaScript](https://img.shields.io/lgtm/grade/javascript/g/thriuin/ogc_search.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/thriuin/ogc_search/context:javascript)
[![Known Vulnerabilities](https://snyk.io/test/github/thriuin/ogc_search/badge.svg?targetFile=requirements.txt)](https://snyk.io/test/github/thriuin/ogc_search?targetFile=requirements.txt)
![GitHub](https://img.shields.io/github/license/thriuin/ogc_search.svg)
![GitHub last commit](https://img.shields.io/github/last-commit/thriuin/ogc_search.svg)
   
## Setup

Some extra steps are required

Download https://raw.githubusercontent.com/open-data/ckanext-canada/master/ckanext/canada/schemas/presets.yaml
to the ckan older 
Download a copy of the WET GCWEB theme files (available at 
http://wet-boew.github.io/wet-boew/docs/versions/dwnld-en.html) to the themes-dist-GCWeb folder

## Installing on Solr 7.6:
- Create a new core using `solr -c <core_name> create`
- In the conf folder remove the managed-schema file and copy the schema-7.6.xml file to schema. Rename it to schema.xml.
- Copy the elevate.xml, synonyms_en.txt, and synonyms_fr.xml to the conf folder 
- Copy the solrconfig-7.6.xml file to conf/solrconfig.xml
