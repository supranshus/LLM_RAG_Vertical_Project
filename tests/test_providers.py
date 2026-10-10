from unittest.mock import MagicMock

import pytest

from config.settings import get_settings
from services.api_provider import ApiProvider
from services.base import NotFoundError
from services.mock_provider import MockProvider


@pytest.fixture
def mock():
    return MockProvider(get_settings().mock_data_dir)


def test_mock_project_crud(mock):
    created = mock.create("projects", {"name": "Fleet"})
    assert mock.get("projects", created["id"])["name"] == "Fleet"
    mock.update("projects", created["id"], {"name": "Renamed"})
    assert mock.list("projects", {"name": "Renamed"})[0]["id"] == created["id"]
    mock.delete("projects", created["id"])
    with pytest.raises(NotFoundError):
        mock.get("projects", created["id"])


def test_mock_documents_and_actions(mock):
    docs = mock.fetch("project_documents", path_params={"project_id": "x"})
    assert {"problem_statement", "sprints", "tasks", "test_cases"} <= docs.keys()
    assert mock.action("project_generate", path_params={"project_id": "x"}) == docs
    # No fixture -> echo, including uploaded file names.
    echoed = mock.action("project_brd", path_params={"project_id": "x"},
                         files={"file": ("brd.pdf", b"..", "application/pdf")})
    assert echoed == {"project_id": "x", "file": "brd.pdf"}


def _api(json_body):
    api = ApiProvider("http://x/api", token="t")
    resp = MagicMock(ok=True, status_code=200, content=b"{}")
    resp.json.return_value = json_body
    api.session.request = MagicMock(return_value=resp)
    return api


def test_api_list_builds_url_and_drops_empty_params():
    api = _api([])
    api.list("projects", {"status": "Draft", "type": ""})
    method, url = api.session.request.call_args.args
    assert (method, url) == ("GET", "http://x/api/projects")
    assert api.session.request.call_args.kwargs["params"] == {"status": "Draft"}
    assert api.session.headers["Authorization"] == "Bearer t"


def test_api_path_params_and_multipart():
    api = _api({})
    api.fetch("project_documents", path_params={"project_id": "p1"})
    assert api.session.request.call_args.args == ("GET", "http://x/api/projects/p1/documents")

    api.action("project_brd", path_params={"project_id": "p1"},
               files={"file": ("brd.pdf", b"..", "application/pdf")})
    args, kwargs = api.session.request.call_args
    assert args == ("POST", "http://x/api/projects/p1/brd")
    assert "files" in kwargs and "json" not in kwargs


def test_api_missing_path_param():
    with pytest.raises(ValueError):
        _api({}).fetch("project_documents")
