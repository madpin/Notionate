from src.schema import load_schema

def test_load_schema():
    """
    Tests that the schema loads correctly.
    """
    schema = load_schema('schema.yaml')
    assert schema is not None
    assert 'version' in schema
    assert 'databases' in schema
