__author__ = "hewgreen"
__license__ = "Apache 2.0"
__date__ = "30/08/2019"

from collections import OrderedDict
# todo maybe add one formatter func to remove [] and underscores?

class fetch_entity_metadata_translation:
    '''
    func should return 1 dict for 1 common datamodel entity which can then be added to the project translated output
    by the main script

    No logic needed to catch duplicates, this is in the main script.

    alias should be dict key and value should be dict of attributes e.g. {"sample":{"alias_of_sample":{ATTRIBUTES GO HERE}}}

    special handling functions are built into the class
    '''

    def __init__(self, translation_params):


        #initialize
        self.bundle = translation_params.get('bundle')
        self.common_entity_type = translation_params.get('common_entity_type')
        self.attribute_translation = translation_params.get('attribute_translation')
        self.bundle_info = translation_params.get('bundle_info')
        self.metadata_files = translation_params.get('metadata_files')
        self.metadata_files_by_uuid = translation_params.get('metadata_files_by_uuid')
        print('WORKING ON ENITY TYPE: {}'.format(self.common_entity_type))


        attribute_value_dict = {}
        for common_attribute, t in self.attribute_translation.items():
            print('WORKING ON ATTRIBUTE: {}'.format(common_attribute))

            # CONFIG REQUIRED hca listed path to attribute (need updating as schema evolves) HCA ENTITY name e.g. project_json is top of list
            self.import_path = t.get('import').get('hca').get('path')
            assert self.import_path, 'Missing import_path in config for attribute {}'.format(self.common_entity_type + '.' + common_attribute)
            # CONFIG REQUIRED used by converter to do all translations
            self.import_method = t.get('import').get('hca').get('method')
            assert self.import_path, 'Missing special_import_method in config for attribute {}'.format(self.common_entity_type + '.' + common_attribute)
            # CONFIG OPTIONAL used to do value translation
            self.import_translation = t.get('import').get('hca').get('translation', None)

            # get attribute value
            attribute_value = getattr(fetch_entity_metadata_translation, self.import_method)(self)
            attribute_value_dict[common_attribute] = attribute_value

        self.translated_entity_metadata = {self.common_entity_type:{attribute_value_dict.get('alias'):attribute_value_dict}} # alias is required


    # Assay Methods
    def get_hca_bundle_uuid(self):
        return self.bundle.get('metadata').get('uuid')

    # Sample Methods
    def highest_biological_entity_get(self):
        # for use when import parent is unknown but general type is biomaterial
        highest_biomaterial = self.bundle_info.ordered_biomaterials[0]
        d = self.metadata_files_by_uuid.get(highest_biomaterial)
        return self.recursive_get(d)

    def get_sample_material_type(self):
        highest_biomaterial_uuid = self.bundle_info.ordered_biomaterials[0]
        highest_biomaterial = self.metadata_files_by_uuid.get(highest_biomaterial_uuid)
        return highest_biomaterial.get('describedBy').split('/')[-1]

    def get_other_biomaterial_attributes(self):
        '''
        Extract extra attributes not captured by common data model schema.
        Look at biomaterials in order of sequence in the graph.
        todo ignore fields that have already been added to the model for the top entity.
        todo this counter may need some refactoring when the design is complete. This is to protect against replacing keys of the same attribute in the column headers of the sdrf. This needs testing with real data.
        '''

        def list_handler(in_list):
            condensed_value = []
            for entry in in_list:
                if isinstance(entry, dict) and 'ontology' in entry:
                    ontology = entry.get('ontology', None)
                    condensed_value.append(ontology)
                elif isinstance(entry, (int, str)):
                    condensed_value.append(entry)
                else:
                    raise Exception('Data type not yet supported at this level. Update the parser to include {}'.format(
                        type(entry)))
            return condensed_value

        extra_attributes = OrderedDict()


        entity_counter = {}

        for biomaterial_uuid in self.bundle_info.ordered_biomaterials:
            # # certain branches can be ignored when exploring the tree.

            biomaterial_metadata = self.metadata_files_by_uuid.get(biomaterial_uuid)
            material_type = biomaterial_metadata.get('describedBy').split('/')[-1]

            # counter
            if material_type in entity_counter:
                entity_counter[material_type] += 1
            else:
                entity_counter[material_type] = 1
            entity_type_count = material_type + '_' + str(entity_counter.get(material_type))


            ignore_top_level = ['schema_type', 'provenance', 'describedBy']
            entity_extra_attributes = {}

            # Explicit metadata parser only supports expected levels of nesting and datatypes at those levels by design but it otherwise it not hard coded.

            for top_level_attribute, top_level_value in biomaterial_metadata.items():
                if top_level_attribute in ignore_top_level:
                    continue
                if isinstance(top_level_value, (dict, list)) == False:
                    entity_extra_attributes[entity_type_count + '.' + top_level_attribute] = top_level_value
                elif isinstance(top_level_value, dict):
                    for mid_level_attribute , mid_level_value in top_level_value.items():
                        if isinstance(mid_level_value, (dict, list)) == False:
                            entity_extra_attributes[entity_type_count + '.' + top_level_attribute + '.' + mid_level_attribute] = mid_level_value
                        elif isinstance(mid_level_value, list):
                            condensed_mid_level_value = list_handler(mid_level_value)
                            entity_extra_attributes[entity_type_count + '.' + top_level_attribute + '.' + mid_level_attribute] = condensed_mid_level_value
                        elif isinstance(mid_level_value, dict):
                            for low_level_attribute, low_level_value in mid_level_value.items():
                                if isinstance(low_level_value, (dict, list)) == False:
                                    entity_extra_attributes[entity_type_count + '.' + top_level_attribute + '.' + mid_level_attribute + '.' + low_level_attribute] = low_level_value
                                else:
                                    raise Exception('4th level nesting detected but not expected. See {}'.format(top_level_attribute + '.' + mid_level_attribute + '.' + low_level_attribute))
                        else:
                            raise Exception('Value type {} not supported'.format(type(mid_level_value)))
                else:
                    assert isinstance(top_level_value, list)
                    entity_extra_attributes[entity_type_count + '.' + top_level_attribute] = list_handler(top_level_value)

                extra_attributes.update(entity_extra_attributes)

        return extra_attributes


    def recursive_get(self, d):
        for key in self.import_path:
            if isinstance(d, list):
                d = [x.get(key, None) for x in d]
            else:
                d = d.get(key, None)
        return d












