"""Mock core datastores module - registered with dependency registry."""

from typing import Any, Dict

# Register with registry on module load
try:
    from fast_dashboards.core.registry import registry

    _REGISTRY_AVAILABLE = True
except ImportError:
    _REGISTRY_AVAILABLE = False


class CassandraWideColumnStore:
    """Mock Cassandra store."""

    enabled = False

    def __init__(self, contact_points=None, port=None, keyspace=None):
        self.contact_points = contact_points or ["127.0.0.1"]
        self.port = port or 9042
        self.keyspace = keyspace

    def connect(self):
        pass

    def disconnect(self):
        pass

    def execute(self, query):
        return []


class CosmosDocumentStore:
    """Mock Cosmos DB store."""

    enabled = False

    def __init__(self, account_uri=None, account_key=None, database=None):
        self.account_uri = account_uri or ""
        self.account_key = account_key or ""
        self.database = database or ""

    def connect(self):
        pass

    def disconnect(self):
        pass

    def get_database(self):
        return None


class DynamoKeyValueStore:
    """Mock DynamoDB store."""

    enabled = False

    def __init__(self, table_name=None, region_name=None):
        self.table_name = table_name or ""
        self.region_name = region_name or "us-east-1"

    def connect(self):
        pass

    def disconnect(self):
        pass


class MongoDocumentStore:
    """Mock MongoDB store."""

    enabled = False

    def __init__(self, uri=None, database=None):
        self.uri = uri or "mongodb://localhost:27017"
        self.database = database or "admin"
        self._db = None

    def connect(self):
        self._db = MockDatabase()

    def disconnect(self):
        self._db = None

    def get_database(self):
        return self._db


class MockDatabase:
    """Mock MongoDB database."""

    def command(self, cmd):
        return {"ok": 1}


class ElasticsearchSearchStore:
    """Mock Elasticsearch store."""

    enabled = False

    def __init__(self, hosts=None, username=None, password=None):
        self.hosts = hosts or ["http://localhost:9200"]
        self.username = username
        self.password = password

    def connect(self):
        pass

    def disconnect(self):
        pass

    def ping(self):
        return True


class RedisKeyValueStore:
    """Mock Redis store."""

    enabled = False

    @classmethod
    def check_health(cls):
        return {"status": "disabled"}


class ScyllaWideColumnStore:
    """Mock ScyllaDB store."""

    enabled = False

    def __init__(self, contact_points=None, port=None, keyspace=None):
        self.contact_points = contact_points or ["127.0.0.1"]
        self.port = port or 9042
        self.keyspace = keyspace

    def connect(self):
        pass

    def disconnect(self):
        pass

    def execute(self, query):
        return []


class PostgresDocumentStore:
    """Mock Postgres store."""

    enabled = False


# Auto-register datastore classes with registry
if _REGISTRY_AVAILABLE:
    registry.register_datastore("CassandraWideColumnStore", CassandraWideColumnStore)
    registry.register_datastore("CosmosDocumentStore", CosmosDocumentStore)
    registry.register_datastore("DynamoKeyValueStore", DynamoKeyValueStore)
    registry.register_datastore("MongoDocumentStore", MongoDocumentStore)
    registry.register_datastore("ElasticsearchSearchStore", ElasticsearchSearchStore)
    registry.register_datastore("RedisKeyValueStore", RedisKeyValueStore)
    registry.register_datastore("ScyllaWideColumnStore", ScyllaWideColumnStore)
    registry.register_datastore("PostgresDocumentStore", PostgresDocumentStore)
