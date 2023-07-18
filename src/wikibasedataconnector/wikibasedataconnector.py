"""wikibot for the GeoScience Knowledgebase
"""
import json
from typing import Optional, Union

import pywikibot as pwb
import requests


class WBDC:
    """
    Constructor and functions
    """
    def __init__(self, site: str) -> None:
        self.site = pwb.Site('en', site)
        self.repo = self.site.data_repository()
        self.mapping_conf = None
        self.config = None
        self.page = None
        self.sparql_endpoint = None
        self.site.login()

    def __add_item(self, page_info: dict, row: list, summary) -> str:
        """Generate new Item in GSKB

        Args:
            item (dict): minimal values needed to create item

        Returns:
            str: Item id generated
        """
        label = description = None
        for info in page_info:
            if info['type'] == 'label':
                label = row[info['idx']]
            elif info['type'] == 'description' and info['idx'] == -1:
                description = info['config']['value']
            elif info['type'] == 'description':
                description = row[info['idx']]
        if label is None or description is None:
            raise ValueError('Missing either label or description to add item')
        data = {
                    'descriptions': {
                        'en': {
                            'language': 'en',
                            'value': description
                        }
                    },
                    'labels': {
                        'en': {
                            'language': 'en',
                            'value': label
                        }
                    }
        }
        # params found at https://www.wikidata.org/w/api.php?action=help&modules=wbeditentity
        params = {
            'action': 'wbeditentity',
            'new': 'item',
            'data': json.dumps(data),
            'token': self.site.tokens['csrf'],
            'summary': summary
        }
        try:
            req = self.site.simple_request(**params)
            results = req.submit()
            return results['entity']['id'] if 'id' in results['entity'] else None
        except Exception as exc:
            print(f'Failed to insert item {label}')
            print(exc)

    def __add_prop(self, page_info: dict, row:list, summary) -> Optional[str]:
        """Generate new property in GSKB

        Args:
            prop (dict): minimal values needed to create property

        Returns:
            Optional[str]: property id generated
        """
        label = description = datatype = None
        for info in page_info:
            if info['type'] == 'label':
                label = row[info['idx']]
            elif info['type'] == 'description' and info['idx'] == -1:
                description = info['config']['value']
            elif info['type'] == 'description':
                description = row[info['idx']]
            elif info['type'] == 'datatype':
                datatype = row[info['idx']]
        if label is None or description is None or datatype is None:
            raise ValueError(
                'Missing minimum info of label, description, datatype needed to add property'
                )
        data = {
                    'datatype': datatype,
                    'descriptions': {
                        'en': {
                            'language': 'en',
                            'value': description
                        }
                    },
                    'labels': {
                        'en': {
                            'language': 'en',
                            'value': label
                        }
                    }
                }

        # params found at https://www.wikidata.org/w/api.php?action=help&modules=wbeditentity
        params = {
            'action': 'wbeditentity',
            'new': 'property',
            'data': json.dumps(data),
            'summary': summary,
            'token': self.site.tokens['csrf']
        }
        try:
            req = self.site.simple_request(**params)
            results = req.submit()
            print(results)
            return results['entity']['id'] if 'id' in results['entity'] else None
        except Exception as exc:
            print(f'Failed to insert property {label}')
            print(exc)

    def __add_source(self, claim: pwb.Claim, ref: dict, row: list, summary: str) -> None:
        """Add sources to claims on item

        Args:
            claim (pwb.Claim): Claim that the source is being added to
            ref (dict): References from conf file
            row (list): Data from file being read
        """
        prop_value = ref['config']['value']
        if ref['idx'] == -1:
            source = pwb.Claim(self.repo, prop_value)
            source.setTarget(ref['value'])
            claim.addSource(source, summary=summary)
        else:
            source = pwb.Claim(self.repo, prop_value)
            source.setTarget(row[ref['idx']])
            claim.addSource(source, summary=summary)

    def __create_page(self, page_id) -> Union[pwb.PropertyPage, pwb.ItemPage]:
        """
        creates either an item page or property page
        """
        if page_id is None:
            raise ValueError('There is no page id')
        if not 'P' in page_id and not 'Q' in page_id:
            raise ValueError
        if 'P' in page_id:
            self.page = pwb.PropertyPage(self.repo, page_id)
        else:
            self.page = pwb.ItemPage(self.repo, page_id)

    def __determine_target(self, target_dict: dict, row: list) -> Union[pwb.Claim, str, pwb.Coordinate]:
        """Handle claim's target type

        Args:
            claim_dict (dict): Claim of interest
            row (list): Data row to index from

        Returns:
            Union[pwb.Claim, str, pwb.Coordinate]: Target ready to attach to claim
        """
        if target_dict['type'] == 'globe-coordinate':
            lat_idx = target_dict['lat']['idx']
            lon_idx = target_dict['lon']['idx']
            lat = float(row[lat_idx])
            lon = float(row[lon_idx])
            return pwb.Coordinate(
                lat=lat,
                lon=lon,
                precision=0.001,
                site=self.site
            )
        if target_dict['idx'] == -1 and target_dict['type'] == 'wikibase-item':
            value = target_dict['value']
            item_id = self.__search_item_id(value, 'item')
            return pwb.ItemPage(self.repo, item_id)
        if target_dict['idx'] == -1:
            return target_dict['value']
        value = row[target_dict['idx']]
        if target_dict['type'] == 'string':
            return value
        if target_dict['type'] == 'monolingualtext':
            value = row[target_dict['idx']]
            lang = target_dict['language'] if 'language' in target_dict else 'en'
            mlt_value = pwb.WbMonolingualText(value, lang)
            return mlt_value
        if target_dict['type'] == 'geo-shape':
            # page that the .map file is at e.g. Data:Neighbourhoods/New_York_City.map
            map_page = target_dict['map_page']
            return pwb.WbGeoShape(map_page, self.repo)
        if target_dict['type'] == 'external-id':
            return value
        if target_dict['type'] == 'quantity':
            value = row[target_dict['idx']]
            amount = target_dict['amount'] if 'amount' in target_dict else None
            # margin of error
            me = target_dict['me'] if 'me' in target_dict else None
            return pwb.WbQuantity(value, amount, me, self.repo)
        if target_dict['type'] == 'time':
            value = row[target_dict['idx']]
            if '-' in value:
                value = ''.join(value.split('-'))
            elif '/' in value:
                value = ''.join(value.split('/'))
            ts = pwb.Timestamp.fromtimestampformat(value)
            return pwb.WbTime.fromTimestamp(ts, precision=11)
        item_id = self.__search_item_id(value, 'item')
        return pwb.ItemPage(self.repo, item_id)

    def __get_item_id(self, unique_id: str) -> Optional[str]:
        """Searches for item id using SPARQL query

        Args:
            unique_id (str): unique identifier of item

        Returns:
            Optional[str]: QID of item in GSKB
        """
        id_prop = self.config['uniqueIDProp']
        query = 'SELECT * WHERE {  ?item wdt:' f'{id_prop} "{unique_id}"' '. }'
        params = {
            'query': query,
            'format': 'json'
        }
        res = requests.get(self.sparql_endpoint, params=params, timeout=100)
        json_res =res.json()
        item_result = (json_res['results']['bindings'][0]['item']['value']
            if 'results' in json_res
            and len(json_res['results']['bindings']) > 0
            and 'item' in json_res['results']['bindings'][0]
            else None)
        return item_result.split('/')[-1] if item_result is not None else None

    async def process(self, row: list) -> None:
        """Process using mapping provided in the conf file
        """
        if 'mapping' not in self.mapping_conf:
            raise ValueError('Mapping is required')
        src = self.mapping_conf['source']
        page_info = self.mapping_conf['mapping']
        summary = src['summary']
        if src['type'] == 'property':
            label = row[src['upsert']['idx']]
            prop_id = self.__search_item_id(label, src['type'])
            if prop_id is None:
                prop_id = self.__add_prop(page_info, row, summary)
            self.__create_page(prop_id)
        elif src['upsert']['matchType'] == 'id':
            unique_id = row[src['upsert']['idx']]
            item_id = self.__get_item_id(unique_id)
            self.__create_page(item_id)
        else:
            label = row[src['upsert']['idx']]
            item_id = self.__search_item_id(label, src['type'])
            if item_id is None:
                item_id = self.__add_item(page_info, row, summary)
            self.__create_page(item_id)
        for opt in page_info:
            if opt['type'] == 'label':
                label = row[opt['idx']]
                self.__upsert_label(label, summary)
            elif opt['type'] == 'description':
                description = opt['config']['value'] if 'config' in opt else row[opt['idx']]
                self.__upsert_description(description, summary)
            elif opt['type'] == 'aliases':
                aliases = row[opt['idx']].split(', ') if row[opt['idx']]  != '' else []
                self.__upsert_aliases(aliases, summary)
            elif opt['type'] == 'claim':
                self.__upsert_claim(opt, row, summary)

    def __search_item_id(self, search_term: str, item_type: str) -> Optional[str]:
        """Makes an API call to find id within the GSKB

        Args:
            item (dict): item attributes in key/value pairs

        Returns:
            Optional[str]: Either the item QID or None if it doesn't exist
        """
        params = {
            'action': 'wbsearchentities',
            'search': search_term,
            'type': item_type,
            'language': 'en',
            'format': 'json'
        }
        req = self.site.simple_request(**params)
        results = req.submit()
        return (results['search'][0]['id']
              if len(results['search']) > 0 and 'id' in results['search'][0]
              else None)

    def set_config(self, settings: dict) -> None:
        """Provide endpoints needed to add to wikibase

        Args:
            settings (dict): Key/Value pairs for endpoint paths
        """
        self.config = settings
        self.sparql_endpoint = settings['SPARQL_ENDPOINT']

    def set_mapping_config(self, mapping: dict) -> None:
        """Adds the mapping configuration

        Args:
            mapping (dict): Loaded JSON mapping
        """
        self.mapping_conf = mapping

    def __set_claim_options(self, claim: pwb.Claim, target: dict, row: list, refs: dict, summary: str) -> None:
        """Add the target and qualifiers to the claim

        Args:
            claim (pwb.Claim): Claim of interest
            target (dict): Target from claim specified in conf
            row (list): Data from file being read
            refs (dict): References from conf
        """
        claim._type = target['type'] # pylint: disable=protected-access
        determined_target = self.__determine_target(target, row)
        claim.setTarget(determined_target)
        self.__upsert_references(claim, refs, row, summary)
        for qualifier in target['qualifiers']:
            self.__upsert_qualifier(claim, qualifier, row, summary)

    def __update_link(self, claim: pwb.Claim, ref: dict, row: list, summary: str) -> None:
        """Updates the url in claim if considered different

        Args:
            claim (pwb.Claim): Source Claim
            ref (dict): Reference to external urls
        """
        for i, _ in enumerate(claim.sources):
            ref_value = ref['config']['value']
            if ref_value in claim.sources[i]:
                claim.removeSource(claim.sources[i][ref_value][0])
                self.__add_source(claim, ref, row, summary)

    def __upsert_claim(self, claim_dict: dict, row: list, summary: str) -> None:
        """Inserts/Updates claims within page

        Args:
            claim_dict (dict): Structure of claim
        """
        claim_value = claim_dict['config']['value']
        claims = self.page.get()['claims']
        refs = self.mapping_conf['reference']
        # if claim value not found in claims at all
        if claim_value not in claims:
            for target in claim_dict['targets']:
                claim = pwb.Claim(self.repo, claim_value)
                self.__set_claim_options(claim, target, row, refs, summary)
                self.page.addClaim(claim, summary=summary)
        # if claim value found, but target not found
        else:
            for target in claim_dict['targets']:
                match_found = False
                # get target to make sure there is always one for comparison
                determined_target = self.__determine_target(target, row)
                for claim in claims[claim_value]:
                    if claim.target_equals(determined_target):
                        self.__upsert_references(claim, refs, row, summary)
                        for qualifier in target['qualifiers']:
                            self.__upsert_qualifier(claim, qualifier, row, summary)
                        match_found = True
                if not match_found:
                    new_claim = pwb.Claim(self.repo, claim_value)
                    self.__set_claim_options(new_claim, target, row, refs, summary)
                    self.page.addClaim(new_claim, summary=summary)

    def __upsert_aliases(self, aliases: str, summary: str) -> None:
        """Adds or updates a label

        Args:
            label (str): Name of item
        """
        page_dict = self.page.get()
        same_aliases = (
        'en' in page_dict['aliases'] 
        and len(page_dict['aliases']['en']) == len(aliases)
        and set(page_dict['aliases']['en']) == set(aliases)
        )
        if not same_aliases:
            self.page.editAliases({'en': aliases }, summary=summary)

    def __upsert_description(self, desc: str, summary: str) -> None:
        """Adds or updates a description

        Args:
            desc (str): description of item
        """
        page_dict = self.page.get()
        if desc != page_dict['labels']['en']:
            self.page.editDescriptions({'en': desc }, summary=summary)

    def __upsert_label(self, label: str, summary: str) -> None:
        """Adds or updates a label

        Args:
            label (str): Name of item
        """
        page_dict = self.page.get()
        if label != page_dict['labels']['en']:
            self.page.editLabels({'en': label }, summary=summary)

    def __upsert_references(self, claim: pwb.Claim, refs: list, row: list, summary: str) -> None:
        """Inserts/updates references into Claim

        Args:
            claim (pwb.Claim): Claim that the reference is being attached to
            refs (list): References provided by the conf file
            claim_dict (dict): Claim object provided by the conf file
            row (list): Data from file being read
        """
        sources = (
            { key : value[0] for x in claim.sources for (key, value) in x.items() }
                if isinstance(claim.sources, list)
                else dict(claim.sources)
            )
        for ref in refs:
            value = ref['value'] if ref['idx'] == -1 else row[ref['idx']]
            if ref['config']['value'] not in sources:
                self.__add_source(claim, ref, row, summary)
            if (ref['config']['value'] in sources
                and value != sources[ref['config']['value']].target):
                self.__update_link(claim, ref, row, summary)

    def __upsert_qualifier(self, claim: pwb.Claim, qualifier_dict: dict, row: list, summary) -> None:
        """Inserts/updates qualifier into Claim

        Args:
            claim (pwb.Claim): Claim that the qualifier is being added on to
            qualifier_dict (dict): qualifier found within claim object provided by the conf file
            row (list): Data from file being read
        """
        qual_claim = qualifier_dict['property']
        qualifier = pwb.Claim(self.repo, qual_claim)
        qualifier._type = qualifier_dict['type']# pylint: disable=protected-access
        target = self.__determine_target(qualifier_dict, row)
        qualifier.setTarget(target)
        if (qual_claim in claim.qualifiers
             and not claim.qualifiers[qual_claim][0].target_equals(target)):
            claim.removeQualifier(claim.qualifiers[qual_claim][0])
            claim.addQualifier(qualifier, summary=summary)
        elif not claim.has_qualifier(qual_claim, target):
            claim.addQualifier(qualifier, summary=summary)

def wait(self, seconds): # pylint: disable=unused-argument
    """Override to remove default throttle of 5 secs
    """
pwb.throttle.Throttle.wait = wait