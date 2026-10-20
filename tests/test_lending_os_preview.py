"""/lending-os/preview is a shareable, static mockup of the Lending OS
dashboard -- an AE can send a single link to a prospect and let them see
the product without needing a login or a real demo account. It reuses the
same fictional Meridian Capital pipeline (Danielle Carter, Marcus Reyes,
the Okafors, Priya Nair) already seeded into the real white_label demo
environment, and is clearly labeled as sample data.

Also covers /lending-os itself, which was restored to its previous
abstract-mockup marketing content after this preview page was added."""


def test_lending_os_preview_renders(client):
    resp = client.get("/lending-os/preview")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Meridian Capital" in body
    assert "Lending OS" in body


def test_lending_os_preview_shows_the_branded_dashboard_banner(client):
    resp = client.get("/lending-os/preview")

    body = resp.get_data(as_text=True)
    assert "images/demo/meridian_capital_banner.jpg" in body
    assert "powered by Ravlo" in body


def test_lending_os_preview_shows_the_meridian_pipeline(client):
    resp = client.get("/lending-os/preview")

    body = resp.get_data(as_text=True)
    assert "Danielle Carter" in body
    assert "Marcus Reyes" in body
    assert "Ade &amp; Lisa Okafor" in body or "Ade & Lisa Okafor" in body
    assert "Priya Nair" in body


def test_lending_os_preview_discloses_sample_data(client):
    resp = client.get("/lending-os/preview")

    body = resp.get_data(as_text=True)
    assert "DEMO PREVIEW" in body
    assert "fictional" in body


def test_lending_os_preview_links_back_to_the_marketing_site(client):
    resp = client.get("/lending-os/preview")

    body = resp.get_data(as_text=True)
    assert 'href="/"' in body
    assert "/lending-os" in body


def test_lending_os_preview_includes_all_five_role_views(client):
    resp = client.get("/lending-os/preview")

    body = resp.get_data(as_text=True)
    assert 'data-role="admin"' in body
    assert 'data-role="lo"' in body
    assert 'data-role="processor"' in body
    assert 'data-role="underwriter"' in body
    assert 'data-role="borrower"' in body


def test_lending_os_preview_shows_the_same_file_from_different_seats(client):
    """The loan officer, processor, underwriter, and borrower views should
    all reference the same underlying Meridian Capital files -- Danielle
    Carter's file connects the loan officer and borrower views, and
    Marcus Reyes / the Okafors connect the processor and underwriter
    views to the broker-owner's company-wide table."""
    resp = client.get("/lending-os/preview")

    body = resp.get_data(as_text=True)
    assert "Chris Nakamura" in body
    assert "Jamie Ortiz" in body
    assert "Devon Marsh" in body
    assert "QUOTE ENGINE" in body
    assert "Approve with Conditions" in body
    assert "Schedule your home inspection" in body


def test_lending_os_preview_role_tabs_are_real_shareable_links(client):
    """Each role tab is an anchor with its own #hash (not a JS-only button
    with no href), so it can be opened in a new browser tab, bookmarked,
    or copied and sent directly to someone -- they land on that role on
    first load instead of always seeing the broker-owner default."""
    resp = client.get("/lending-os/preview")

    body = resp.get_data(as_text=True)
    assert 'href="#admin"' in body
    assert 'href="#loan-officer"' in body
    assert 'href="#processor"' in body
    assert 'href="#underwriter"' in body
    assert 'href="#borrower"' in body


def test_lending_os_preview_admin_tab_mirrors_the_real_company_dashboard(client):
    """The broker-owner tab was rebuilt to mirror the real internal admin
    page (admin/company_dashboard.html) instead of an invented layout --
    same sidebar sections, same KPI cards, same Applicant Assignments /
    Team / Workspace Controls panels, populated with the Meridian
    Capital sample data."""
    resp = client.get("/lending-os/preview")

    body = resp.get_data(as_text=True)
    assert "Meridian Capital Lending Command Center" in body
    assert "APPLICANT ASSIGNMENTS" in body
    assert "WORKSPACE CONTROLS" in body
    assert "Team Members" in body
    assert "Renata Castillo" in body
    assert "Company Admin" in body


def test_lending_os_preview_internal_roles_share_one_visual_language(client):
    """The Loan Officer, Processor, and Underwriter tabs used to look like
    a different product (a warm navy/gold "Meridian" shell) next to the
    Broker-Owner tab's real admin look (Ravlo's dark blue rc- theme).
    They were rebuilt on the same rc-shell components and each role's
    real sidebar structure so switching tabs doesn't feel jarring."""
    resp = client.get("/lending-os/preview")

    body = resp.get_data(as_text=True)
    assert 'id="loShell"' in body
    assert 'id="processorShell"' in body
    assert 'id="underwriterShell"' in body
    assert 'id="adminShell"' in body
    # Real per-role sidebar sections/labels, not the old invented nav.
    assert "Loan Officer Workspace" in body
    assert "Processor Workspace" in body
    assert "Underwriter Workspace" in body
    assert "Loan Queue" in body
    assert "Decision Queue" in body
    # The old Meridian-branded shell chrome is gone.
    assert "app-shell" not in body
    assert 'class="app-hero"' not in body


def test_lending_os_preview_borrower_tab_mirrors_the_real_borrower_dashboard(client):
    """The borrower tab used a custom-invented layout (a stepper, a "Your
    Team" contact card) with no real counterpart. Rebuilt it to mirror the
    real borrower/dashboard.html + ravlo_borrower_base.html: the same
    topbar + horizontal nav tabs, hero, 4-stat row, and two-column main
    grid (Application Progress / Active Loan / Recent Documents on the
    left, Actions / Checklist / Open Conditions / Subscription on the
    right), populated with Danielle Carter's file."""
    resp = client.get("/lending-os/preview")

    body = resp.get_data(as_text=True)
    assert "Borrower Dashboard" in body
    assert "Application Progress" in body
    assert "Active Loan" in body
    assert "Recent Documents" in body
    assert "Your Next Items" in body
    assert "Open Conditions" in body
    assert "Your Plan" in body
    # The real horizontal nav tabs, not a custom stepper.
    assert ">Loans</a>" in body
    assert ">Subscription</a>" in body


def test_lending_os_marketing_page_still_renders(client):
    resp = client.get("/lending-os")

    assert resp.status_code == 200
