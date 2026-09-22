"""Regression test for the "Open in Design Studio" quick-card on a Build
Project's detail page.

build_project_detail.html links to Design Studio with `project_id=project.id`
-- the same pattern already used (and handled) by its Build Studio and
Project Build siblings on that same page. But design_studio() never read
`project_id` at all, so clicking it opened a completely blank workspace
with no blueprint/exterior image, no prefilled fields, and a dead
"Open Build Studio" companion link (its href depends on a `project` template
var that was never passed in). Not a literal 404, but functionally a dead
end for anyone who hasn't converted their Build Project into a Deal yet.
"""
from LoanMVP.models.admin import Company
from LoanMVP.models.renovation_models import BuildProject
from LoanMVP.models.user_model import User

from tests.conftest import login_as


def _make_investor(db_session, email="builder@example.com"):
    company = Company(name="Build Co", is_active=True, subscription_tier="team", max_users=10)
    db_session.add(company)
    db_session.commit()

    user = User(email=email, role="investor", is_active=True, company_id=company.id)
    db_session.add(user)
    db_session.commit()
    return user


def test_design_studio_seeds_exterior_image_from_build_project(db_session, client):
    user = _make_investor(db_session)
    project = BuildProject(
        user_id=user.id,
        project_name="Maple Grove Residences",
        development_type="single_family",
        concept_render_url="https://example.com/exterior-render.jpg",
        blueprint_url="https://example.com/blueprint.jpg",
    )
    db_session.add(project)
    db_session.commit()

    login_as(client, user)
    resp = client.get(f"/investor/deal-studio/design-studio?project_id={project.id}")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "https://example.com/exterior-render.jpg" in body
    assert f'value="{project.id}"' in body


def test_design_studio_does_not_leak_another_users_build_project(db_session, client):
    owner = _make_investor(db_session, email="owner@example.com")
    other = _make_investor(db_session, email="other@example.com")
    project = BuildProject(
        user_id=owner.id,
        project_name="Private Project",
        concept_render_url="https://example.com/private-render.jpg",
    )
    db_session.add(project)
    db_session.commit()

    login_as(client, other)
    resp = client.get(f"/investor/deal-studio/design-studio?project_id={project.id}")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "https://example.com/private-render.jpg" not in body
