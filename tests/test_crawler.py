from tools.maps_crawler.crawl import batches, is_blocked, search_url, shape_row


def test_search_url_is_encoded_and_english():
    assert search_url("skin clinic in Saket, Delhi") == "https://www.google.com/maps/search/skin%20clinic%20in%20Saket%2C%20Delhi?hl=en"


def test_captcha_and_unusual_traffic_pages_are_detected():
    assert is_blocked("https://www.google.com/sorry/index?continue=x", "")
    assert is_blocked("https://www.google.com/maps/search/x", "Our systems have detected unusual traffic from your computer network")
    assert not is_blocked("https://www.google.com/maps/search/x", "Dermatologist 4.8(120) Skin clinic")


def test_shape_row_merges_list_card_and_detail_panel():
    card = {"name": "Glow Clinic", "rating": "4.8 stars 120 Reviews", "category_address": "Skin care clinic", "ad": False}
    detail = {"ok": True, "website": "", "phone": "011 2345 6789", "address": "12 Saket Road, Delhi", "links": ["https://glow.example/book"]}
    row = shape_row(card, detail, "https://www.google.com/maps/place/Glow+Clinic/@1,2")
    assert row["category_address"] == "Skin care clinic · 12 Saket Road, Delhi" and row["detail_read"] is True
    assert row["links"] == ["https://glow.example/book"] and row["phone"] == "011 2345 6789" and row["website"] == ""


def test_batches():
    assert batches(list(range(7)), 3) == [[0, 1, 2], [3, 4, 5], [6]]


def test_unmatched_panel_is_not_treated_as_read():
    card = {"name": "Glow Clinic", "rating": "", "category_address": "Skin clinic", "ad": False}
    row = shape_row(card, {"ok": False, "website": "", "phone": "", "address": "", "links": []}, "u")
    assert row["detail_read"] is False  # so the lead stays 'not checked' instead of becoming a false 'no website'
