from __future__ import annotations

import json
import random
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.enums import RoleName
from app.models.approval import ApprovalPolicy
from app.models.citation import ReferenceSource, ScientificCitation
from app.models.integration import IntegrationConfiguration
from app.models.rule import (
    RuleDefinition,
    RuleDependency,
    RuleInheritance,
    RuleScope,
    RuleVersion,
)
from app.models.ticket import Ticket
from app.models.user import Role, User, UserRole
from app.models.validation import HistoricalReview, TestCase
from app.rules.checksum import rule_checksum
from app.security.auth import hash_password

MARKETS = ["US", "UK", "DE", "FR", "ES", "IT", "JP", "AU", "CA"]
BRANDS = ["Drug A", "Drug B", "Drug C", "Drug X"]
AREAS = ["Cardiovascular", "Respiratory", "Oncology", "Immunology", "Vaccines"]
MATERIALS = [
    "Promotional",
    "Medical Communication",
    "Scientific Response",
    "Digital Advertisement",
    "Detail Aid",
    "Email",
    "Website",
]

USERS = [
    ("admin@mlr-ruleops.local", "ChangeMe!Admin1", "Alex Rivera", [RoleName.ADMIN]),
    ("mlr.admin@mlr-ruleops.local", "ChangeMe!Mlr1", "Priya Shah", [RoleName.MLR_ADMIN]),
    ("medical@mlr-ruleops.local", "ChangeMe!Med1", "Jordan Hale, MD", [RoleName.MEDICAL_REVIEWER]),
    ("regulatory@mlr-ruleops.local", "ChangeMe!Reg1", "Elena Voss", [RoleName.REGULATORY_REVIEWER]),
    ("requester@mlr-ruleops.local", "ChangeMe!Req1", "Sam Okonkwo", [RoleName.BUSINESS_REQUESTER]),
    ("auditor@mlr-ruleops.local", "ChangeMe!Aud1", "Chris Nguyen", [RoleName.AUDITOR]),
    ("viewer@mlr-ruleops.local", "ChangeMe!View1", "Morgan Lee", [RoleName.VIEWER]),
]


def seed_if_empty(db: Session, reviews: int = 200) -> None:
    if db.query(User).first():
        return
    seed_all(db, reviews)


def seed_all(db: Session, reviews: int = 200) -> None:
    _roles_users(db)
    _citations(db)
    _policies(db)
    _integrations(db)
    rules = _rules(db)
    _tickets(db)
    generate_historical_reviews(db, reviews)
    _test_cases(db)
    db.flush()


def _roles_users(db: Session) -> None:
    role_map = {}
    for name in RoleName:
        role = Role(name=name.value, description=f"{name.value} role")
        db.add(role)
        db.flush()
        role_map[name.value] = role
    for email, password, full_name, roles in USERS:
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=hash_password(password),
            department="Medical Affairs",
        )
        db.add(user)
        db.flush()
        for r in roles:
            db.add(UserRole(user_id=user.id, role_id=role_map[r.value].id))


def _citations(db: Session) -> None:
    demo = [
        ("CIT-2020-001", "Outcomes of Drug A in stable cardiovascular disease", "Smith J, Patel R", 2020, "Cardio Journal"),
        ("CIT-2026-004", "Drug A cardiovascular outcomes: 2026 randomized trial", "Chen L, Alvarez M", 2026, "NEJM Analog"),
    ]
    extras = [
        ("CIT-2018-011", "Long-term safety of Drug B", "Ibrahim K", 2018, "Resp Review"),
        ("CIT-2019-022", "Oncology signal detection methods", "Wu S", 2019, "Onco Methods"),
        ("CIT-2021-033", "Immunology endpoint hierarchy", "Garcia P", 2021, "Immunol Today"),
        ("CIT-2021-044", "Vaccine strain update guidance", "Nilsen T", 2021, "Vax Policy"),
        ("CIT-2022-055", "Drug C real-world evidence", "Brown A", 2022, "RWE Letters"),
        ("CIT-2022-066", "Cross-market disclaimer patterns", "Okada H", 2022, "Reg Affairs"),
        ("CIT-2023-077", "Drug X routing constraints", "Meyer D", 2023, "Ops Science"),
        ("CIT-2023-088", "Promotional claim substantiation", "Ross E", 2023, "MLR Quarterly"),
        ("CIT-2024-099", "Digital advertisement local rules", "Dupont F", 2024, "EU Promo"),
        ("CIT-2024-101", "JP language-specific disclosures", "Sato Y", 2024, "JP Reg"),
        ("CIT-2024-110", "AU PI hyperlink conventions", "Clarke N", 2024, "TGA Notes"),
        ("CIT-2025-120", "CA bilingual disclaimer study", "Tremblay C", 2025, "Health Can"),
        ("CIT-2025-130", "UK MHRA wording refresh", "Hughes B", 2025, "UKRA"),
        ("CIT-2025-140", "FR ANSM office address variants", "Moreau L", 2025, "ANSM Brief"),
        ("CIT-2025-150", "DE Fachinfo citation style", "Keller M", 2025, "BfArM"),
        ("CIT-2025-160", "ES local legal footer", "Ruiz I", 2025, "AEMPS"),
        ("CIT-2025-170", "IT scientific response template", "Bianchi G", 2025, "AIFA"),
        ("CIT-2026-180", "Vaccine season 2026 composition", "Park J", 2026, "WHO Analog"),
    ]
    for cid, title, authors, year, journal in demo + extras:
        db.add(
            ScientificCitation(
                citation_id=cid,
                title=title,
                authors=authors,
                year=year,
                journal=journal,
                doi=f"10.1000/demo.{cid.lower()}",
                study_type="RCT" if "trial" in title.lower() or year >= 2020 else "Observational",
                status="SYNTHETIC_DEMO",
                source="Synthetic Demo Dataset",
                is_synthetic=True,
                notes="Synthetic demo citation metadata. Not a real publication.",
                verified_at=datetime.now(UTC),
                verified_by="seed",
            )
        )
    db.add(
        ReferenceSource(
            source_id="SRC-US-PI-DRUGA",
            title="Drug A US Prescribing Information (synthetic)",
            source_type="prescribing_information",
            snippet="See full prescribing information for boxed warning and contraindications.",
            relevance_note="Referenced by US Drug A disclaimer family",
        )
    )


def _policies(db: Session) -> None:
    specs = [
        ("scientific_accuracy", '["DISCLAIMER","SCIENTIFIC_ACCURACY"]', '["MEDICAL_REVIEWER","MLR_ADMIN"]', "Scientific accuracy dual control", 10),
        ("universal_scope", '{"scope":"UNIVERSAL"}', '["MLR_ADMIN","REGULATORY_REVIEWER","ADMIN"]', "Enterprise rule governance board", 20),
        ("critical_risk", '{"risk":"CRITICAL"}', '["MEDICAL_REVIEWER","REGULATORY_REVIEWER","MLR_ADMIN"]', "Critical risk multi-party approval", 5),
        ("high_risk", '{"risk":"HIGH"}', '["MLR_ADMIN"]', "High risk MLR administration", 30),
        ("standard", "{}", '["MLR_ADMIN"]', "Standard MLR change approval", 100),
    ]
    for name, cond, roles, label, pri in specs:
        db.add(
            ApprovalPolicy(
                name=name,
                description=label,
                condition_json=cond,
                required_roles=roles,
                governance_label=label,
                priority=pri,
            )
        )


def _integrations(db: Session) -> None:
    for name, provider, notes in [
        ("internal", "internal", "Generic REST/webhook path is active"),
        ("servicenow", "servicenow", "NOT_CONFIGURED until credentials are supplied"),
        ("jira", "jira", "NOT_CONFIGURED until credentials are supplied"),
    ]:
        db.add(
            IntegrationConfiguration(
                name=name,
                provider=provider,
                status="ACTIVE" if provider == "internal" else "NOT_CONFIGURED",
                notes=notes,
            )
        )


def _add_rule(
    db: Session,
    rule_id: str,
    name: str,
    rule_type: str,
    category: str,
    scope_type: str,
    body: dict,
    market=None,
    brand=None,
    area=None,
    material=None,
    language="EN",
    versions: int = 1,
    priority: int = 100,
) -> RuleDefinition:
    rule = RuleDefinition(
        rule_id=rule_id,
        name=name,
        rule_type=rule_type,
        rule_category=category,
        status="ACTIVE",
        priority=priority,
        description=name,
    )
    db.add(rule)
    db.flush()
    db.add(
        RuleScope(
            rule_id=rule.id,
            scope_type=scope_type,
            market=market,
            country=market,
            language=language,
            brand=brand,
            therapeutic_area=area,
            material_type=material,
            effective_from=datetime.now(UTC) - timedelta(days=400),
        )
    )
    parent = None
    for n in range(1, versions + 1):
        payload = json.loads(json.dumps(body))
        payload["rule_id"] = rule_id
        if n < versions and rule_type == "TEXT":
            payload["content"] = payload.get("content", "") + f" [v{n} archive]"
        ver = RuleVersion(
            rule_id=rule.id,
            version_number=n,
            version_label=f"v{n}",
            body_json=json.dumps(payload),
            checksum_sha256=rule_checksum(payload),
            created_by="seed",
            change_summary=f"Seed version {n}",
            is_production=(n == versions),
            parent_version_id=parent,
        )
        db.add(ver)
        db.flush()
        parent = ver.id
        if n == versions:
            rule.production_version_id = ver.id
    return rule


def _rules(db: Session) -> list[RuleDefinition]:
    created: list[RuleDefinition] = []
    # Hero rule
    created.append(
        _add_rule(
            db,
            "RULE-US-DRUGA-CV-014",
            "US Drug A cardiovascular promotional disclaimer",
            "TEXT",
            "DISCLAIMER",
            "MARKET_BRAND",
            {
                "rule_type": "TEXT",
                "rule_id": "RULE-US-DRUGA-CV-014",
                "field": "disclaimer",
                "scope": {"market": "US", "brand": "Drug A", "therapeutic_area": "Cardiovascular"},
                "content": (
                    "Drug A (generic name) is indicated to reduce cardiovascular risk in appropriate adults. "
                    "This promotional claim is supported by Smith et al., 2020 (CIT-2020-001). "
                    "See full prescribing information. "
                    "[Synthetic Demo Dataset — citation metadata is synthetic.]"
                ),
                "references": [{"type": "scientific_citation", "id": "CIT-2020-001"}],
                "flagged_terms": ["cure", "miracle"],
                "required_phrases": [],
            },
            market="US",
            brand="Drug A",
            area="Cardiovascular",
            material="Promotional",
            versions=3,
            priority=10,
        )
    )
    created.append(
        _add_rule(
            db,
            "RULE-US-CV-002",
            "US cardiovascular generic disclaimer",
            "TEXT",
            "DISCLAIMER",
            "MARKET",
            {
                "rule_type": "TEXT",
                "rule_id": "RULE-US-CV-002",
                "field": "disclaimer",
                "scope": {"market": "US", "therapeutic_area": "Cardiovascular"},
                "content": "US cardiovascular materials must include a market-level safety disclaimer.",
                "references": [],
            },
            market="US",
            area="Cardiovascular",
            material="Promotional",
            versions=2,
        )
    )
    created.append(
        _add_rule(
            db,
            "RULE-UNIV-DISCLAIMER-001",
            "Universal promotional disclaimer baseline",
            "TEXT",
            "DISCLAIMER",
            "UNIVERSAL",
            {
                "rule_type": "TEXT",
                "rule_id": "RULE-UNIV-DISCLAIMER-001",
                "field": "disclaimer",
                "scope": {},
                "content": "All promotional materials require an approved disclaimer.",
                "references": [],
            },
            versions=2,
        )
    )
    created.append(
        _add_rule(
            db,
            "RULE-DRUGA-BRAND-001",
            "Drug A brand-level claim language",
            "TEXT",
            "CLAIM",
            "BRAND",
            {
                "rule_type": "TEXT",
                "rule_id": "RULE-DRUGA-BRAND-001",
                "field": "claim",
                "scope": {"brand": "Drug A"},
                "content": "Do not describe Drug A as a cure.",
                "flagged_terms": ["cure"],
            },
            brand="Drug A",
        )
    )
    created.append(
        _add_rule(
            db,
            "RULE-SCI-CV-ACCURACY-001",
            "Cardiovascular scientific accuracy overlay",
            "TEXT",
            "SCIENTIFIC_ACCURACY",
            "SCIENTIFIC_ACCURACY",
            {
                "rule_type": "TEXT",
                "rule_id": "RULE-SCI-CV-ACCURACY-001",
                "field": "scientific_accuracy",
                "scope": {"therapeutic_area": "Cardiovascular"},
                "content": "Cardiovascular efficacy claims require a current outcomes citation.",
                "references": [{"type": "scientific_citation", "id": "CIT-2020-001"}],
            },
            area="Cardiovascular",
        )
    )
    created.append(
        _add_rule(
            db,
            "RULE-LOGIC-DRUGX-MY-001",
            "Drug X Market Y routing",
            "LOGIC",
            "ROUTING",
            "MARKET_BRAND",
            {
                "rule_type": "LOGIC",
                "rule_id": "RULE-LOGIC-DRUGX-MY-001",
                "scope": {"market": "UK", "brand": "Drug X"},
                "when": {
                    "all": [
                        {"field": "brand", "operator": "eq", "value": "Drug X"},
                        {"field": "market", "operator": "eq", "value": "UK"},
                    ]
                },
                "actions": [
                    {"type": "route", "target": "Reviewer Z"},
                    {"type": "flag", "value": "Constraint W"},
                ],
            },
            market="UK",
            brand="Drug X",
            versions=2,
        )
    )

    # Additional catalog
    idx = 0
    for market in MARKETS:
        for brand, area, material, cat in [
            ("Drug A", "Respiratory", "Email", "DISCLAIMER"),
            ("Drug B", "Oncology", "Detail Aid", "CLAIM"),
            ("Drug C", "Immunology", "Website", "DISCLOSURE"),
            ("Drug X", "Vaccines", "Digital Advertisement", "PI_LINK"),
        ]:
            idx += 1
            rid = f"RULE-{market}-{brand.replace(' ', '').upper()}-{idx:03d}"
            created.append(
                _add_rule(
                    db,
                    rid,
                    f"{market} {brand} {area} {cat.lower()}",
                    "TEXT",
                    cat,
                    "MARKET_BRAND",
                    {
                        "rule_type": "TEXT",
                        "rule_id": rid,
                        "field": cat.lower(),
                        "scope": {"market": market, "brand": brand, "therapeutic_area": area},
                        "content": f"{market} {brand} {area} {material} {cat} text. Office address variation {idx}.",
                        "references": [],
                    },
                    market=market,
                    brand=brand,
                    area=area,
                    material=material,
                )
            )
            if len(created) >= 52:
                break
        if len(created) >= 52:
            break

    # Logic extras
    created.append(
        _add_rule(
            db,
            "RULE-LOGIC-US-ONCO-ROUTE",
            "US oncology medical review route",
            "LOGIC",
            "ROUTING",
            "MARKET",
            {
                "rule_type": "LOGIC",
                "rule_id": "RULE-LOGIC-US-ONCO-ROUTE",
                "when": {
                    "all": [
                        {"field": "market", "operator": "eq", "value": "US"},
                        {"field": "therapeutic_area", "operator": "eq", "value": "Oncology"},
                    ]
                },
                "actions": [{"type": "route", "target": "Oncology Medical Review"}, {"type": "require_review"}],
            },
            market="US",
            area="Oncology",
        )
    )

    # Inheritance + dependencies
    hero = next(r for r in created if r.rule_id == "RULE-US-DRUGA-CV-014")
    market_cv = next(r for r in created if r.rule_id == "RULE-US-CV-002")
    univ = next(r for r in created if r.rule_id == "RULE-UNIV-DISCLAIMER-001")
    sci = next(r for r in created if r.rule_id == "RULE-SCI-CV-ACCURACY-001")
    brand = next(r for r in created if r.rule_id == "RULE-DRUGA-BRAND-001")
    db.add(RuleInheritance(child_rule_id=hero.id, parent_rule_id=market_cv.id, inheritance_type="OVERRIDE"))
    db.add(RuleInheritance(child_rule_id=market_cv.id, parent_rule_id=univ.id, inheritance_type="OVERRIDE"))
    db.add(RuleDependency(rule_id=hero.id, depends_on_rule_id=sci.id, dependency_type="OVERLAY", notes="Scientific accuracy overlay"))
    db.add(RuleDependency(rule_id=hero.id, depends_on_rule_id=brand.id, dependency_type="REQUIRES", notes="Brand claim language"))
    db.add(RuleDependency(rule_id=hero.id, depends_on_rule_id=univ.id, dependency_type="INHERITS", notes="Universal disclaimer baseline"))
    # more deps among catalog
    for a, b in zip(created[6:12], created[12:18]):
        db.add(RuleDependency(rule_id=a.id, depends_on_rule_id=b.id, dependency_type="RELATED", notes="Catalog pairing"))
    return created


def _tickets(db: Session) -> None:
    demo = Ticket(
        ticket_number="TKT-1001",
        external_id="DEMO-CV-DISCLAIMER-2026",
        source_system="INTERNAL",
        title="US Cardiovascular Disclaimer Citation Update",
        description=(
            "Update the US cardiovascular disclaimer for Drug A to include the new 2026 clinical trial "
            "citation and remove reference to the 2020 study."
        ),
        requester_name="Sam Okonkwo",
        requester_email="requester@mlr-ruleops.local",
        priority="HIGH",
        status="RECEIVED",
        market_hint="US",
        brand_hint="Drug A",
        therapeutic_area_hint="Cardiovascular",
        language_hint="EN",
        is_demo_seed=True,
        due_date=datetime.now(UTC) + timedelta(days=3),
    )
    db.add(demo)
    extras = [
        ("TKT-1002", "UK Drug X routing update", "If Drug X is mentioned in Market Y (UK), route to Reviewer Z and flag Constraint W.", "UK", "Drug X", "BUSINESS_LOGIC_CHANGE"),
        ("TKT-1003", "DE Fachinfo footer refresh", "Update DE immunology website disclosure for Drug C.", "DE", "Drug C", None),
        ("TKT-1004", "JP language disclosure", "Correct restricted terminology in JP vaccines digital advertisement for Drug X.", "JP", "Drug X", None),
        ("TKT-1005", "FR office address variation", "Change office-address variation on FR Drug B oncology detail aid.", "FR", "Drug B", None),
        ("TKT-1006", "CA bilingual disclaimer", "Update CA bilingual disclaimer wording for Drug A email.", "CA", "Drug A", None),
        ("TKT-1007", "AU PI hyperlink", "Change prescribing-information hyperlink for AU Drug A respiratory email.", "AU", "Drug A", None),
        ("TKT-1008", "ES legal footer", "Update localized legal disclaimer for ES Drug C website.", "ES", "Drug C", None),
        ("TKT-1009", "IT scientific response", "Replace scientific citation on IT scientific response template.", "IT", "Drug B", None),
        ("TKT-1010", "Universal claim language", "Swap old product claim for new claim on universal Drug A brand rule.", "US", "Drug A", None),
    ]
    for num, title, desc, market, brand, ctype in extras:
        db.add(
            Ticket(
                ticket_number=num,
                external_id=num,
                source_system="INTERNAL",
                title=title,
                description=desc,
                requester_name="Sam Okonkwo",
                requester_email="requester@mlr-ruleops.local",
                priority="MEDIUM",
                status="RECEIVED",
                market_hint=market,
                brand_hint=brand,
                change_type=ctype,
            )
        )


def generate_historical_reviews(db: Session, count: int = 200) -> int:
    existing = db.query(HistoricalReview).count()
    start = existing + 1
    rng = random.Random(42 + existing)
    created = 0
    for i in range(start, start + count):
        bucket = i % 10
        if bucket in {0, 1, 2}:
            market, brand, area, material = "US", "Drug A", "Cardiovascular", "Promotional"
            if bucket == 0:
                content = (
                    "Promotional detail for Drug A in the United States. Cardiovascular risk reduction discussed. "
                    "Supported by the 2020 outcomes study. See prescribing information."
                )
                tags = ["us-druga-cv", "citation-2020"]
            elif bucket == 1:
                content = (
                    "Promotional detail for Drug A US cardiovascular. References the 2026 clinical trial. "
                    "See full prescribing information."
                )
                tags = ["us-druga-cv", "citation-2026"]
            else:
                content = (
                    "Drug A US cardiovascular promotional email. Disclaimer present. Borderline claim language, "
                    "no study year mentioned."
                )
                tags = ["us-druga-cv", "borderline"]
        elif bucket == 3:
            market, brand, area, material = "UK", "Drug X", "Vaccines", "Digital Advertisement"
            content = "Drug X mentioned for Market Y / UK campaign. Route-sensitive content."
            tags = ["drugx-uk"]
        elif bucket == 4:
            market, brand, area, material = "US", "Drug B", "Oncology", "Detail Aid"
            content = "US oncology detail aid for Drug B. Unrelated to Drug A cardiovascular disclaimer."
            tags = ["negative", "unrelated-brand"]
        else:
            market = rng.choice(MARKETS)
            brand = rng.choice(["Drug B", "Drug C", "Drug X"])
            area = rng.choice(["Respiratory", "Oncology", "Immunology", "Vaccines"])
            material = rng.choice(MATERIALS)
            content = f"{market} {brand} {area} {material} content without Drug A cardiovascular claims."
            tags = ["negative", "unrelated-market"]
        db.add(
            HistoricalReview(
                review_id=f"REV-{i:05d}",
                market=market,
                brand=brand,
                therapeutic_area=area,
                language="EN",
                material_type=material,
                content=content,
                expected_flags="[]",
                expected_route=None,
                historical_decision=rng.choice(["APPROVED", "APPROVED", "REVISE", "APPROVED"]),
                is_synthetic=True,
                tags=json.dumps(tags),
                created_at=datetime.now(UTC) - timedelta(days=rng.randint(1, 400)),
            )
        )
        created += 1
    return created


def _test_cases(db: Session) -> None:
    cases = [
        ("hierarchy-market-brand", "US", "Drug A", "Cardiovascular", "Promotional", "Drug A US CV disclaimer 2020 study"),
        ("hierarchy-market-only", "US", "Drug B", "Cardiovascular", "Promotional", "Generic US CV"),
        ("unrelated-jp", "JP", "Drug C", "Immunology", "Website", "JP immunology website"),
        ("drugx-uk-route", "UK", "Drug X", "Vaccines", "Digital Advertisement", "Drug X UK mention"),
        ("borderline-no-year", "US", "Drug A", "Cardiovascular", "Email", "Drug A cardiovascular without year"),
    ]
    for name, market, brand, area, material, content in cases:
        db.add(
            TestCase(
                name=name,
                description=name,
                market=market,
                brand=brand,
                therapeutic_area=area,
                material_type=material,
                content=content,
                expected_flags="[]",
            )
        )


if __name__ == "__main__":
    from app.db.session import SessionLocal
    from app.db.base import Base
    from app.db.session import engine
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
        db.commit()
        print("Seed complete")
    finally:
        db.close()
