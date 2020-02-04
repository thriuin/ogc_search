# ogc_search
Django based search for the Canadian Open Government Portal 

This project uses a Django framework web application as a thin frontend to Solr to do searching of datasets and 
proactive disclosure data for the Open Government Portal. Instead of using default CKAN Solr 6 cores, data is 
loaded into custom Solr cores that customized specifically to support Canada's two official languages and fast data exprting.

[![Total alerts](https://img.shields.io/lgtm/alerts/g/thriuin/ogc_search.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/thriuin/ogc_search/alerts/)
[![Language grade: JavaScript](https://img.shields.io/lgtm/grade/javascript/g/thriuin/ogc_search.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/thriuin/ogc_search/context:javascript)
[![Language grade: JavaScript](https://img.shields.io/lgtm/grade/javascript/g/thriuin/ogc_search.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/thriuin/ogc_search/context:javascript)
[![Known Vulnerabilities](https://snyk.io/test/github/thriuin/ogc_search/badge.svg?targetFile=requirements.txt)](https://snyk.io/test/github/thriuin/ogc_search?targetFile=requirements.txt)
![GitHub](https://img.shields.io/github/license/thriuin/ogc_search.svg)
![GitHub last commit](https://img.shields.io/github/last-commit/thriuin/ogc_search.svg)
   
## Setup

OGC Search is a Django 2.1 application that runs on Python 3.6 or higher. It also requires Solr 6.6.2,
which is compatible with the version of Solr currently in use with Open Canada.

 #### ogc_search
 
 Clone the GitHub OGC Search project: https://github.com/open-data/ogc_search. Create a new 
 python 3.7 virtual environment for the project and install the requirements from the
 `requirements.txt` file.
 
 `pip install -r requirements.txt`
 
 OGC Search is built using [Django 2.1](https://www.djangoproject.com/).
 Familiarity with Django is prerequisite to developing with the OGC Search. 
 * **NLTK Data** OGC Search uses the NLTK python library and requires the Punkt tokenizers which are 
   available from https://www.nltk.org/nltk_data/. These datafiles must be accessible
   to the Python virtual environment. It is not necessary to download the
   entire NLTK corpus.
 * OGC Search is a bilingual application that uses the standard gettext library
   to support localisation. On Windows, it will be necessary to install the [**gettext**
   library](https://mlocati.github.io/articles/gettext-iconv-windows.html).
   
  
 
 #### CKAN YAML and JSON Files
  OGC Search reads information that describes the CKAN datasets and proactive disclosure data
  types from the ckanext-scheming YAML files. The proactive disclosure files are available on [GitHub](https://github.com/open-data/ckanext-canada/tree/master/ckanext/canada/tables/)
  as are the [CKAN dataset files](https://github.com/open-data/ckanext-canada/tree/master/ckanext/canada/schemas).
  It also requires two JSON files for international [currency](https://github.com/open-data/ckanext-canada/blob/master/bin/download_currency.py) and 
  [country](https://github.com/open-data/ckanext-canada/blob/master/bin/download_country.py) codes. These files
  are often copied to the /ckan folder, but the location can be configured
  
 #### WET-BOEW Template Files 
  Download and extract a copy of the [WET GCWEB theme files](http://wet-boew.github.io/wet-boew/docs/versions/dwnld-en.html) 
  to a new local folder, for example /themes-dist-GCWeb located in the project root.

 #### Setting up Solr
  Download and install Apache Solr 6.6.x from the [Apache repo](https://archive.apache.org/dist/lucene/solr/6.6.6/)
  After installing, create at least one new Solr core for the default search. Once the core
  has been created, customize it for OGC Search.
- As the `solr` user create a new core: `solr -c <core_name> create`
- In the /conf folder of the new Solr core, remove the file `managed-schema` and copy the new
  `schema.xml`  and `solrconfig.xml` from the corresponding search application project solr folder. 
- Copy the `/lang` folder and the `synonyms_en.txt` and `synonyms_fr.txt` files from the project to the new Solr core /conf folder 
- Verify the new core is working using the Solr admin interface

 #### Static Files
  
  OGC Search has a large number of static files. As per Django, these files are 
  collected from each project and in development mode can be served up
  by the Django server. These files go into a /static folder that often is 
  created in the root of the project file for development, but this can be configured
  as desired.
  
 #### Settings.py 
  
  As is usual in Django, application settings are stored in a settings.py
  file that is saved to the project folder /ogc_search/ogc_search/settings.py.
  An example settings files is provided: `/ogc_search/ogc_search/settings.sample.py`.
  
 ## Loading Data
 
 The open data Solr search core is populated by CKAN, however for all the
 proactive disclosure searches, 'contracts' for example, the Solr core is populated
 by a script that reads the CKAN recombinant CSV output file for the 
 corresponding proactive disclosure type and saves the data to the
 search optimized core.
 
 Controlled list values for the proactive disclosure data is read from the
 corresponding YAML table definition file.
 
 ## Exporting Data
  
  OGC Search uses the binary data export feature of Solr to perform fast and
  efficient export or search results to a CSV file.

## License

Unless otherwise noted, the source code of this project is covered under Crown Copyright, Government of Canada, and is distributed under the [MIT License](LICENSE).

The Canada wordmark and related graphics associated with this distribution are protected under trademark law and copyright law. No permission is granted to use them outside the parameters of the Government of Canada's corporate identity program. For more information, see [Federal identity requirements](https://www.canada.ca/en/treasury-board-secretariat/topics/government-communications/federal-identity-requirements.html).
