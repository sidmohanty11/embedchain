import os
import shutil
from unittest.mock import patch

import pytest
from chromadb.config import Settings

from embedchain import App
from embedchain.config import AppConfig, ChromaDbConfig
from embedchain.vectordb.chroma import ChromaDB

os.environ["OPENAI_API_KEY"] = "test-api-key"


@pytest.fixture
def chroma_db():
    return ChromaDB(config=ChromaDbConfig(host="test-host", port="1234"))


@pytest.fixture
def app_with_settings():
    chroma_config = ChromaDbConfig(allow_reset=True, dir="test-db")
    chroma_db = ChromaDB(config=chroma_config)
    app_config = AppConfig(collect_metrics=False)
    return App(config=app_config, db=chroma_db)


@pytest.fixture(scope="session", autouse=True)
def cleanup_db():
    yield
    try:
        shutil.rmtree("test-db")
    except OSError as e:
        print("Error: %s - %s." % (e.filename, e.strerror))


@pytest.mark.skip(reason="ChromaDB client needs to be mocked")
def test_chroma_db_init_with_host_and_port(chroma_db):
    settings = chroma_db.client.get_settings()
    assert settings.chroma_server_host == "test-host"
    assert settings.chroma_server_http_port == "1234"


@pytest.mark.skip(reason="ChromaDB client needs to be mocked")
def test_chroma_db_init_with_basic_auth():
    chroma_config = {
        "host": "test-host",
        "port": "1234",
        "chroma_settings": {
            "chroma_client_auth_provider": "chromadb.auth.basic.BasicAuthClientProvider",
            "chroma_client_auth_credentials": "admin:admin",
        },
    }

    db = ChromaDB(config=ChromaDbConfig(**chroma_config))
    settings = db.client.get_settings()
    assert settings.chroma_server_host == "test-host"
    assert settings.chroma_server_http_port == "1234"
    assert settings.chroma_client_auth_provider == chroma_config["chroma_settings"]["chroma_client_auth_provider"]
    assert settings.chroma_client_auth_credentials == chroma_config["chroma_settings"]["chroma_client_auth_credentials"]


@patch("embedchain.vectordb.chroma.chromadb.Client")
def test_app_init_with_host_and_port(mock_client):
    host = "test-host"
    port = "1234"
    config = AppConfig(collect_metrics=False)
    db_config = ChromaDbConfig(host=host, port=port)
    db = ChromaDB(config=db_config)
    _app = App(config=config, db=db)

    called_settings: Settings = mock_client.call_args[0][0]
    assert called_settings.chroma_server_host == host
    assert called_settings.chroma_server_http_port == port


@patch("embedchain.vectordb.chroma.chromadb.Client")
def test_app_init_with_host_and_port_none(mock_client):
    db = ChromaDB(config=ChromaDbConfig(allow_reset=True, dir="test-db"))
    _app = App(config=AppConfig(collect_metrics=False), db=db)

    called_settings: Settings = mock_client.call_args[0][0]
    assert called_settings.chroma_server_host is None
    assert called_settings.chroma_server_http_port is None


def test_chroma_db_duplicates_throw_warning(caplog):
    db = ChromaDB(config=ChromaDbConfig(allow_reset=True, dir="test-db"))
    app = App(config=AppConfig(collect_metrics=False), db=db)
    app.db.collection.add(embeddings=[[0, 0, 0]], ids=["0"])
    app.db.collection.add(embeddings=[[0, 0, 0]], ids=["0"])
    assert "Insert of existing embedding ID: 0" in caplog.text
    assert "Add of existing embedding ID: 0" in caplog.text
    app.db.reset()


def test_chroma_db_duplicates_collections_no_warning(caplog):
    db = ChromaDB(config=ChromaDbConfig(allow_reset=True, dir="test-db"))
    app = App(config=AppConfig(collect_metrics=False), db=db)
    app.set_collection_name("test_collection_1")
    app.db.collection.add(embeddings=[[0, 0, 0]], ids=["0"])
    app.set_collection_name("test_collection_2")
    app.db.collection.add(embeddings=[[0, 0, 0]], ids=["0"])
    assert "Insert of existing embedding ID: 0" not in caplog.text
    assert "Add of existing embedding ID: 0" not in caplog.text
    app.db.reset()
    app.set_collection_name("test_collection_1")
    app.db.reset()


def test_chroma_db_collection_init_with_default_collection():
    db = ChromaDB(config=ChromaDbConfig(allow_reset=True, dir="test-db"))
    app = App(config=AppConfig(collect_metrics=False), db=db)
    assert app.db.collection.name == "embedchain_store"


def test_chroma_db_collection_init_with_custom_collection():
    db = ChromaDB(config=ChromaDbConfig(allow_reset=True, dir="test-db"))
    app = App(config=AppConfig(collect_metrics=False), db=db)
    app.set_collection_name(name="test_collection")
    assert app.db.collection.name == "test_collection"


def test_chroma_db_collection_set_collection_name():
    db = ChromaDB(config=ChromaDbConfig(allow_reset=True, dir="test-db"))
    app = App(config=AppConfig(collect_metrics=False), db=db)
    app.set_collection_name("test_collection")
    assert app.db.collection.name == "test_collection"


def test_chroma_db_collection_changes_encapsulated():
    db = ChromaDB(config=ChromaDbConfig(allow_reset=True, dir="test-db"))
    app = App(config=AppConfig(collect_metrics=False), db=db)
    app.set_collection_name("test_collection_1")
    assert app.db.count() == 0

    app.db.collection.add(embeddings=[0, 0, 0], ids=["0"])
    assert app.db.count() == 1

    app.set_collection_name("test_collection_2")
    assert app.db.count() == 0

    app.db.collection.add(embeddings=[0, 0, 0], ids=["0"])
    app.set_collection_name("test_collection_1")
    assert app.db.count() == 1
    app.db.reset()
    app.set_collection_name("test_collection_2")
    app.db.reset()


def test_chroma_db_collection_add_with_skip_embedding(app_with_settings):
    # Start with a clean app
    app_with_settings.db.reset()

    assert app_with_settings.db.count() == 0

    app_with_settings.db.add(
        embeddings=[[0, 0, 0]],
        documents=["document"],
        metadatas=[{"url": "url_1", "doc_id": "doc_id_1"}],
        ids=["id"],
        skip_embedding=True,
    )

    assert app_with_settings.db.count() == 1

    data = app_with_settings.db.get(["id"], limit=1)
    expected_value = {
        "documents": ["document"],
        "embeddings": None,
        "ids": ["id"],
        "metadatas": [{"url": "url_1", "doc_id": "doc_id_1"}],
        "data": None,
        "uris": None,
    }

    assert data == expected_value

    data_without_citations = app_with_settings.db.query(
        input_query=[0, 0, 0], where={}, n_results=1, skip_embedding=True
    )
    expected_value_without_citations = ["document"]
    assert data_without_citations == expected_value_without_citations

    app_with_settings.db.reset()


def test_chroma_db_collection_add_with_invalid_inputs(app_with_settings):
    # Start with a clean app
    app_with_settings.db.reset()

    assert app_with_settings.db.count() == 0

    with pytest.raises(ValueError):
        app_with_settings.db.add(
            embeddings=[[0, 0, 0]],
            documents=["document", "document2"],
            metadatas=[{"value": "somevalue"}],
            ids=["id"],
            skip_embedding=True,
        )

    assert app_with_settings.db.count() == 0

    with pytest.raises(ValueError):
        app_with_settings.db.add(
            embeddings=None,
            documents=["document", "document2"],
            metadatas=[{"value": "somevalue"}],
            ids=["id"],
            skip_embedding=True,
        )

    assert app_with_settings.db.count() == 0
    app_with_settings.db.reset()


def test_chroma_db_collection_collections_are_persistent():
    db = ChromaDB(config=ChromaDbConfig(allow_reset=True, dir="test-db"))
    app = App(config=AppConfig(collect_metrics=False), db=db)
    app.set_collection_name("test_collection_1")
    app.db.collection.add(embeddings=[[0, 0, 0]], ids=["0"])
    del app

    db = ChromaDB(config=ChromaDbConfig(allow_reset=True, dir="test-db"))
    app = App(config=AppConfig(collect_metrics=False), db=db)
    app.set_collection_name("test_collection_1")
    assert app.db.count() == 1

    app.db.reset()


def test_chroma_db_collection_parallel_collections():
    db1 = ChromaDB(config=ChromaDbConfig(allow_reset=True, dir="test-db", collection_name="test_collection_1"))
    app1 = App(
        config=AppConfig(collect_metrics=False),
        db=db1,
    )
    db2 = ChromaDB(config=ChromaDbConfig(allow_reset=True, dir="test-db", collection_name="test_collection_2"))
    app2 = App(
        config=AppConfig(collect_metrics=False),
        db=db2,
    )

    # cleanup if any previous tests failed or were interrupted
    app1.db.reset()
    app2.db.reset()

    app1.db.collection.add(embeddings=[0, 0, 0], ids=["0"])
    assert app1.db.count() == 1
    assert app2.db.count() == 0

    app1.db.collection.add(embeddings=[[0, 0, 0], [1, 1, 1]], ids=["1", "2"])
    app2.db.collection.add(embeddings=[0, 0, 0], ids=["0"])

    app1.set_collection_name("test_collection_2")
    assert app1.db.count() == 1
    app2.set_collection_name("test_collection_1")
    assert app2.db.count() == 3

    # cleanup
    app1.db.reset()
    app2.db.reset()


def test_chroma_db_collection_ids_share_collections():
    db1 = ChromaDB(config=ChromaDbConfig(allow_reset=True, dir="test-db"))
    app1 = App(config=AppConfig(collect_metrics=False), db=db1)
    app1.set_collection_name("one_collection")
    db2 = ChromaDB(config=ChromaDbConfig(allow_reset=True, dir="test-db"))
    app2 = App(config=AppConfig(collect_metrics=False), db=db2)
    app2.set_collection_name("one_collection")

    app1.db.collection.add(embeddings=[[0, 0, 0], [1, 1, 1]], ids=["0", "1"])
    app2.db.collection.add(embeddings=[0, 0, 0], ids=["2"])

    assert app1.db.count() == 3
    assert app2.db.count() == 3

    # cleanup
    app1.db.reset()
    app2.db.reset()


def test_chroma_db_collection_reset():
    db1 = ChromaDB(config=ChromaDbConfig(allow_reset=True, dir="test-db"))
    app1 = App(config=AppConfig(collect_metrics=False), db=db1)
    app1.set_collection_name("one_collection")
    db2 = ChromaDB(config=ChromaDbConfig(allow_reset=True, dir="test-db"))
    app2 = App(config=AppConfig(collect_metrics=False), db=db2)
    app2.set_collection_name("two_collection")
    db3 = ChromaDB(config=ChromaDbConfig(allow_reset=True, dir="test-db"))
    app3 = App(config=AppConfig(collect_metrics=False), db=db3)
    app3.set_collection_name("three_collection")
    db4 = ChromaDB(config=ChromaDbConfig(allow_reset=True, dir="test-db"))
    app4 = App(config=AppConfig(collect_metrics=False), db=db4)
    app4.set_collection_name("four_collection")

    app1.db.collection.add(embeddings=[0, 0, 0], ids=["1"])
    app2.db.collection.add(embeddings=[0, 0, 0], ids=["2"])
    app3.db.collection.add(embeddings=[0, 0, 0], ids=["3"])
    app4.db.collection.add(embeddings=[0, 0, 0], ids=["4"])

    app1.db.reset()

    assert app1.db.count() == 0
    assert app2.db.count() == 1
    assert app3.db.count() == 1
    assert app4.db.count() == 1

    # cleanup
    app2.db.reset()
    app3.db.reset()
    app4.db.reset()


def test_chroma_db_collection_query(app_with_settings):
    app_with_settings.db.reset()

    assert app_with_settings.db.count() == 0

    app_with_settings.db.add(
        embeddings=[[0, 0, 0]],
        documents=["document"],
        metadatas=[{"url": "url_1", "doc_id": "doc_id_1"}],
        ids=["id"],
        skip_embedding=True,
    )

    assert app_with_settings.db.count() == 1

    app_with_settings.db.add(
        embeddings=[[0, 1, 0]],
        documents=["document2"],
        metadatas=[{"url": "url_2", "doc_id": "doc_id_2"}],
        ids=["id2"],
        skip_embedding=True,
    )

    assert app_with_settings.db.count() == 2

    data_without_citations = app_with_settings.db.query(
        input_query=[0, 0, 0], where={}, n_results=2, skip_embedding=True
    )
    expected_value_without_citations = ["document", "document2"]
    assert data_without_citations == expected_value_without_citations

    data_with_citations = app_with_settings.db.query(
        input_query=[0, 0, 0], where={}, n_results=2, skip_embedding=True, citations=True
    )
    expected_value_with_citations = [
        (
            "document",
            {
                "url": "url_1",
                "doc_id": "doc_id_1",
                "score": 0.0,
            },
        ),
        (
            "document2",
            {
                "url": "url_2",
                "doc_id": "doc_id_2",
                "score": 1.0,
            },
        ),
    ]
    assert data_with_citations == expected_value_with_citations

    app_with_settings.db.reset()
