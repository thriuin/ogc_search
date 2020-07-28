#!/usr/bin/env bash

wget https://github.com/open-data/ckanext-canada/blob/master/ckanext/canada/schemas/presets.yaml -O $1/presets.yaml
wget https://github.com/open-data/ckanext-canada/blob/master/ckanext/canada/tables/briefingt.yaml -O $1/briefingt.yaml
wget https://github.com/open-data/ckanext-canada/blob/master/ckanext/canada/tables/contracts.yaml -O $1/contracts.yaml
wget https://github.com/open-data/ckanext-canada/blob/master/ckanext/canada/tables/experiment.yaml -O $1/experiment.yaml
wget https://github.com/open-data/ckanext-canada/blob/master/ckanext/canada/tables/grants.yaml -O $1/grants.yaml
wget https://github.com/open-data/ckanext-canada/blob/master/ckanext/canada/tables/nap.yaml -O $1/nap.yaml
wget https://github.com/open-data/ckanext-canada/blob/master/ckanext/canada/tables/service.yaml -O $1/service.yaml
wget https://github.com/open-data/ckanext-canada/blob/master/ckanext/canada/tables/qpnotes.yaml -O $1/qpnotes.yaml
wget https://github.com/open-data/ckanext-canada/blob/master/ckanext/canada/tables/choices/minister.json -O $1/minister.json
wget https://github.com/open-data/ckanext-canada/blob/master/ckanext/canada/tables/choices/country.json -O $1/country.json
wget https://github.com/open-data/ckanext-canada/blob/master/ckanext/canada/tables/choices/currency.json -O $1/currency.json
wget https://github.com/open-data/ckanext-canada/blob/staging/ckanext/canada/schemas/prop.yaml -O $1/prop.yaml
