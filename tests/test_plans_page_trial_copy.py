"""The /plans page's free-trial badge said "2 weeks free" while every
plan card's own CTA underneath it says "15 days free" -- same trial,
two different lengths implied on one page."""


def test_plans_page_trial_badge_matches_the_actual_trial_length(client):
    resp = client.get("/plans")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "15 days free on every plan" in body
    assert "2 weeks free" not in body
