'''
gets metadata for a hca project uuid
'''
# todo automatically update config with new paths to attributes as HCA schema evolves
# todo ref attributes are for linking. We need a method to fill these fields. For now they have placeholders only!


__author__ = "hewgreen"
__license__ = "Apache 2.0"
__date__ = "30/08/2019"

from hca.dss import DSSClient
import json
from ingest.api.ingestapi import IngestApi
import converter_helper_func
from get_common_model_entity_metadata import fetch_entity_metadata_translation
import copy


def get_dss_generator(hca_project_uuid):
    # files.project_json.provenance.document_id project uuid you want to retreive
    # exists files.project_json.provenance.document_id removes test bundles
    # "files.analysis_process_json.type.text": "analysis" look at primary bundles only don't return analysis bundles

    query = {
        "query": {
            "bool": {
                "must": [
                    {
                        "match": {
                            "files.project_json.provenance.document_id": ""
                        }
                    },
                    {
                        "exists": {
                            "field": "files.project_json.provenance.document_id"
                        }
                    }
                ],
                "must_not": [
                    {
                        "match": {
                            "files.analysis_process_json.type.text": "analysis"
                        }
                    }
                ]
            }
        }
    }

    query.get("query").get("bool").get("must")[0].get("match")[
        "files.project_json.provenance.document_id"] = hca_project_uuid

    dss_client = DSSClient(swagger_url="https://dss.data.humancellatlas.org/v1/swagger.json")
    bundle_generator = dss_client.post_search.iterate(replica="aws", es_query=query, output_format="raw")
    total_hits = dss_client.post_search(replica="aws", es_query=query, output_format="raw").get('total_hits')
    return (bundle_generator, total_hits)

def get_hca_entity_types(ingest_api_url="http://api.ingest.data.humancellatlas.org"):
    ingest_api = IngestApi(url=ingest_api_url)
    res = ingest_api.get_schemas(high_level_entity="type", latest_only=True)
    hca_schemas = {}
    for schema in res:
        concreteEntity = schema.get('concreteEntity')
        domainEntity = schema.get('domainEntity')
        if domainEntity not in hca_schemas:
            hca_schemas[domainEntity] = [concreteEntity + '_json']
        else:
            hca_schemas[domainEntity].append(concreteEntity + '_json')
    return hca_schemas

def check_bundle_assumptions(hca_schemas):
    # Atlas cannot handle multi entities in either duplicated non branched DAG or DAG bubbles
    assert 'biomaterial' in hca_schemas, 'HCA no longer have biomaterial schemas!'
    assert len(metadata_files.get('links_json', [])) == 1, 'More than one links.json file in bundle'
    assert len(metadata_files.get('project_json', [])) == 1, 'More than one project.json file in bundle'
    for biomaterial_type_entity in hca_schemas.get('biomaterial'):  # todo add support for multiple chained entities
        assert len(metadata_files.get(biomaterial_type_entity,
                                      [])) <= 1, 'More than one {} in dataset! Atlas cannot handle this at this time.'.format(
            biomaterial_type_entity)
    assert 1 <= len(metadata_files.get('sequence_file_json', [])) <= 3, 'Wrong number of sequencing files.'

    # todo add checks for assay type assumptions to flag technologies that aren't supported

def get_metadata_files_by_uuid(metadata_files):
    # lookup by uuid is frequently used
    metadata_files_by_uuid = {}
    for type, file_list in metadata_files.items():
        if type != 'links_json':
            for file in file_list:
                uuid = file.get('provenance').get('document_id')
                metadata_files_by_uuid[uuid] = file
    return metadata_files_by_uuid

def get_entity_granularity(common_entity_type):
    # common data model, hardcoded granularity assumptions not part of config at this time

    granularity={'project': 'one_entity_per_project',
                 'study': 'one_entity_per_project',
                 'publication': 'skip',
                 'contact': 'skip',
                 'sample': 'one_entity_per_hca_assay',
                 'assay_data': 'one_entity_per_hca_assay',
                 'singlecell_assay': 'one_entity_per_hca_assay',
                 'analysis': 'skip',
                 'microarray_assay': 'skip',
                 'sequencing_assay': 'skip',
                 'data_file': 'skip',
                 'protocol': 'protocol_handling'}
    assert common_entity_type in granularity, "{} is an unrecognised entity type. Add to the granularity dict in code.".format(common_entity_type)
    return granularity.get(common_entity_type)

if __name__ == '__main__':

    # temp params
    hca_project_uuid = 'cc95ff89-2e68-4a08-a234-480eca21ce79'


    translation_config_file = 'temp_config.json'
    # translation_config_file = 'mapping_HCA_to_datamodel.json'
    # translation_config_file = 'temp_temp_conf.json'


    with open(translation_config_file) as f:
        translation_config = json.load(f)

    # temp function to show hca coverage in config
    # converter_helper_func.conf_coverage(translation_config_file)

    # initialise
    get_generator = get_dss_generator(hca_project_uuid)
    res = get_generator[0]
    total_hits = get_generator[1]
    hca_entities = get_hca_entity_types()

    project_translated_output = {}
    detected_protocols = []
    x = []


    for bundle in res:

        bundle_graph = converter_helper_func.bundle_info(bundle)
        metadata_files = bundle.get('metadata').get('files')
        metadata_files_by_uuid = get_metadata_files_by_uuid(metadata_files)
        # check_bundle_assumptions(hca_schemas) # todo turn on after testing

        for common_entity_type, attribute_translation in translation_config.items():
            entity_granularity =  get_entity_granularity(common_entity_type)
            translation_params = {
                            'bundle': bundle,
                            'common_entity_type' : common_entity_type,
                            'attribute_translation' : attribute_translation,
                            'bundle_graph' : bundle_graph,
                            'metadata_files' : metadata_files,
                            'metadata_files_by_uuid' : metadata_files_by_uuid,
                            'translation_config' : translation_config
            }

            if entity_granularity == 'one_entity_per_project':
                if common_entity_type in project_translated_output: # skip if already there
                    continue
                else:
                    translated_entity_metadata = fetch_entity_metadata_translation(translation_params).translated_entity_metadata
                    project_translated_output.update(translated_entity_metadata)

            elif entity_granularity == 'one_entity_per_hca_assay':
                # always get then add to dict or create new entry
                translated_entity_metadata = fetch_entity_metadata_translation(translation_params).translated_entity_metadata
                if common_entity_type in project_translated_output:
                    project_translated_output.get(common_entity_type).update(translated_entity_metadata.get(common_entity_type))
                    # project_translated_output[common_entity_type] = {**project_translated_output.get(common_entity_type), **translated_entity_metadata}
                else:
                    # project_translated_output[common_entity_type] = translated_entity_metadata
                    project_translated_output.update(translated_entity_metadata)
            elif entity_granularity == 'protocol_handling':
                # check by alias first before grabbing all metadata. Skip if seen before.
                assert common_entity_type == 'protocol', 'This handling is only for protocols'

                if 'protocol' not in project_translated_output:
                    project_translated_output['protocol'] = {}

                current_protocols = hca_entities.get(common_entity_type)
                protocol_files = [a for b in [c for (d, c) in {e: f for (e, f) in metadata_files.items() if e in current_protocols}.items()] for a in b]

                for file in protocol_files:
                    protocol_alias = file.get('protocol_core', None).get('protocol_id', None)
                    protocol_uuid = file.get('provenance').get('document_id')
                    assert protocol_alias, 'Hard coded assumption failed to find protocol alias. Quick fix needed.'

                    if protocol_alias not in detected_protocols:
                        detected_protocols.append(protocol_alias)

                        # # augment config paths with specific protocol type
                        # temp_translation_config = copy.deepcopy(translation_config)
                        # for common_attribute_name, t in translation_config.get('protocol').items():
                        #     hca_conf = t.get('import', None).get('hca', None)
                        #     if hca_conf:
                        #         path = hca_conf.get('path', None)
                        #         assert path and isinstance(path, list), 'Missing path in config. See attribute: {}'.format(common_attribute_name)
                        #         if path[0] == 'protocol_json':
                        #             path[0] = file.get('describedBy').split('/')[-1] + '_json'

                        translated_entity_metadata = fetch_entity_metadata_translation(translation_params, protocol_uuid).translated_entity_metadata
                        x.append(translated_entity_metadata.get('protocol')) # test
                        # translation_config = copy.deepcopy(temp_translation_config)  # reset translation config prior to augmentation

                        project_translated_output['protocol'].update(translated_entity_metadata.get('protocol'))



            elif entity_granularity == 'skip':
                # nested entites are handled at the higher level when called by the config
                # also some entities aren't used for HCA data
                continue

    # temp writing out json for inspection
    import json
    with open('temp_out.json', 'w') as f:
        json.dump(project_translated_output, f)
    # print(project_translated_output)

