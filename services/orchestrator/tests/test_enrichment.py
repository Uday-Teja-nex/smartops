import pytest
from app.enrichment import EnrichmentRequest, enrich


class Provider:
    def review_event_evidence_base64(self, prompt, images, schema):
        assert images == ['aA==']
        assert 'Do not confirm intent' in prompt
        return self.result


def test_enrichment_has_no_incident_adjudication_fields():
    provider = Provider()
    provider.result = {'observations': ['Person visible.'], 'recommendedActions': ['Check access log.'],
                       'limitations': ['Authorization cannot be established from this image.'], 'severity': 'critical'}
    result = enrich(provider, EnrichmentRequest(incidentId='one', eventType='restricted_entry',
                                               measuredSummary='Rule fired', imageBase64='aA=='))
    assert 'severity' not in result.model_dump()
    assert result.observations == ['Person visible.']


@pytest.mark.parametrize('result', [{'observations': []}, {'observations': ['x' * 301], 'recommendedActions': [], 'limitations': []}])
def test_invalid_enrichment_does_not_become_operator_copy(result):
    provider = Provider()
    provider.result = result
    with pytest.raises(ValueError):
        enrich(provider, EnrichmentRequest(incidentId='one', eventType='test', measuredSummary='', imageBase64='aA=='))
