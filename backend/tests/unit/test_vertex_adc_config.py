import json

from app.config import Settings


def test_auto_provider_uses_adc_quota_project(tmp_path):
    credentials = tmp_path / "application_default_credentials.json"
    credentials.write_text(
        json.dumps(
            {
                "type": "authorized_user",
                "quota_project_id": "vertex-project",
            }
        )
    )
    settings = Settings(
        llm_provider="auto",
        google_application_credentials=str(credentials),
        gcp_project_id="",
    )

    assert settings.adc_credentials_path == str(credentials)
    assert settings.resolved_gcp_project_id == "vertex-project"
    assert settings.resolved_llm_provider == "gemini"


def test_missing_configured_credentials_fall_back_to_standard_adc(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    credentials = tmp_path / ".config/gcloud/application_default_credentials.json"
    credentials.parent.mkdir(parents=True)
    credentials.write_text(
        json.dumps(
            {
                "type": "authorized_user",
                "quota_project_id": "quota-project",
            }
        )
    )
    settings = Settings(
        llm_provider="auto",
        google_application_credentials="./missing-service-account.json",
        gcp_project_id="",
    )

    assert settings.adc_credentials_path == str(credentials)
    assert settings.resolved_gcp_project_id == "quota-project"
    assert settings.resolved_llm_provider == "gemini"


def test_cloud_runtime_project_enables_vertex_without_local_adc(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    settings = Settings(
        llm_provider="auto",
        google_application_credentials="./missing-service-account.json",
        gcp_project_id="cloud-project",
    )

    assert settings.adc_credentials_path == ""
    assert settings.resolved_gcp_project_id == "cloud-project"
    assert settings.resolved_llm_provider == "gemini"
