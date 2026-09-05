import csv
import io

from app.models.configuration import ConfigurationMatrixRow
from app.rules.dsl import ChangeIntent
from app.rules.matrix import ConfigurationMatrixResolver, row_to_dict


CSV_HEADER = (
    "config_id,market,country,language,brand,therapeutic_area,string_type,"
    "old_value,new_value,static_link,rule_switch,additional_params,rule_id,status"
)


def test_matrix_has_78_rows_and_20_plus_languages(db):
    rows = db.query(ConfigurationMatrixRow).all()
    assert len(rows) == 78
    languages = {r.language for r in rows}
    assert len(languages) >= 20
    ids = [r.config_id for r in rows]
    assert len(ids) == len(set(ids))
    hero = next(r for r in rows if r.config_id == "CFG-US-DRUGA-CV-DISCLAIMER-EN")
    assert hero.rule_id == "RULE-US-DRUGA-CV-014"
    assert hero.language == "EN"
    assert hero.string_type == "DISCLAIMER"
    assert "CIT-2020-001" in hero.old_value


def test_hero_resolve_via_matrix_matcher(db):
    intent = ChangeIntent(
        change_type="TEXT_STRING_UPDATE",
        intent="UPDATE_DISCLAIMER",
        market={"value": "US", "confidence": 0.99},
        brand={"value": "Drug A", "confidence": 0.99},
        therapeutic_area={"value": "Cardiovascular", "confidence": 0.97},
        language={"value": "EN", "confidence": 0.9},
        string_type={"value": "DISCLAIMER", "confidence": 0.93},
        rule_category={"value": "DISCLAIMER", "confidence": 0.93},
        old_value="CIT-2020-001",
        citation_to_remove="CIT-2020-001",
    )
    rows = [row_to_dict(r) for r in db.query(ConfigurationMatrixRow).all()]
    result = ConfigurationMatrixResolver().resolve(intent, rows)
    assert result.status == "MATRIX_MATCHED"
    assert result.selected is not None
    assert result.selected.config_id == "CFG-US-DRUGA-CV-DISCLAIMER-EN"
    assert result.selected.rule_id == "RULE-US-DRUGA-CV-014"


def test_list_and_resolve_api(client, auth_headers):
    listed = client.get("/api/v1/configurations", headers=auth_headers)
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["count"] == 78
    assert body["language_count"] >= 20
    hero = client.get("/api/v1/configurations/CFG-US-DRUGA-CV-DISCLAIMER-EN", headers=auth_headers)
    assert hero.status_code == 200
    assert hero.json()["rule_id"] == "RULE-US-DRUGA-CV-014"

    resolved = client.post(
        "/api/v1/configurations/resolve",
        headers=auth_headers,
        json={
            "market": "US",
            "brand": "Drug A",
            "therapeutic_area": "Cardiovascular",
            "string_type": "DISCLAIMER",
            "language": "EN",
            "old_value": "CIT-2020-001",
            "citation_to_remove": "CIT-2020-001",
        },
    )
    assert resolved.status_code == 200, resolved.text
    data = resolved.json()
    assert data["status"] == "MATRIX_MATCHED"
    assert data["selected"]["config_id"] == "CFG-US-DRUGA-CV-DISCLAIMER-EN"
    assert data["selected"]["rule_id"] == "RULE-US-DRUGA-CV-014"


def test_csv_header_only_import_reports_zero(client, auth_headers):
    empty = client.post(
        "/api/v1/configurations/import",
        headers=auth_headers,
        files={"file": ("empty.csv", b"", "text/csv")},
    )
    assert empty.status_code == 200, empty.text
    assert empty.json()["control_count"] == "0 records"

    header_only = client.post(
        "/api/v1/configurations/import",
        headers=auth_headers,
        files={"file": ("header.csv", CSV_HEADER.encode(), "text/csv")},
    )
    assert header_only.status_code == 200, header_only.text
    assert header_only.json()["imported"] == 0
    assert header_only.json()["updated"] == 0
    assert header_only.json()["control_count"] == "0 records"


def test_csv_one_row_delta_updates_old_value(client, auth_headers, db):
    target = (
        db.query(ConfigurationMatrixRow)
        .filter(ConfigurationMatrixRow.config_id != "CFG-US-DRUGA-CV-DISCLAIMER-EN")
        .first()
    )
    assert target is not None
    config_id = target.config_id
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_HEADER.split(","))
    writer.writerow(
        [
            config_id,
            target.market,
            target.country,
            target.language,
            target.brand,
            target.therapeutic_area,
            target.string_type,
            "updated static text from daily delta",
            target.new_value or "",
            target.static_link,
            target.rule_switch,
            target.additional_params,
            target.rule_id,
            target.status,
        ]
    )
    payload = buf.getvalue()
    resp = client.post(
        "/api/v1/configurations/import",
        headers=auth_headers,
        files={"file": ("delta.csv", payload.encode(), "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["updated"] == 1
    assert resp.json()["control_count"] == "1 records"
    db.expire_all()
    refreshed = db.query(ConfigurationMatrixRow).filter(ConfigurationMatrixRow.config_id == config_id).one()
    assert refreshed.old_value == "updated static text from daily delta"


def test_dashboard_active_configurations(client, auth_headers):
    data = client.get("/api/v1/analytics/dashboard", headers=auth_headers).json()
    assert data["active_configurations"] == 78
