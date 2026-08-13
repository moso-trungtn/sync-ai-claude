import fpdiff

def fp(banners=(), structure=(), images=(), unextractable=False, pages=1):
    return {"version": 1, "format": "pdf", "unextractable": unextractable,
            "banners": sorted(banners), "structure": sorted(structure),
            "images": sorted(images), "pages": pages}

BASE = fp(banners=["ELITE ACCESS DSCR PLUS SPECIAL", "NEW YORK SPECIAL .75 improvement"],
          structure=["# # # #", "FICO >= # LTV <= #"])

def kinds(changes):
    return [c.kind for c in changes]

def test_rates_only_change_is_silent():
    assert fpdiff.diff(BASE, fp(banners=BASE["banners"], structure=BASE["structure"])) == []

def test_new_banner_is_promo_new():
    new = fp(banners=BASE["banners"] + [".375 Price Improvement for loan amounts >$350K"],
             structure=BASE["structure"])
    changes = fpdiff.diff(BASE, new)
    assert kinds(changes) == ["PROMO_NEW"]
    assert changes[0].materiality == "high"
    assert "$350K" in changes[0].detail

def test_removed_banner_is_promo_expired():
    new = fp(banners=BASE["banners"][:1], structure=BASE["structure"])
    assert kinds(fpdiff.diff(BASE, new)) == ["PROMO_EXPIRED"]

def test_similar_add_remove_collapses_to_promo_changed():
    new = fp(banners=["ELITE ACCESS DSCR PLUS SPECIAL",
                      "NEW YORK SPECIAL .50 improvement"],   # .75 → .50
             structure=BASE["structure"])
    assert kinds(fpdiff.diff(BASE, new)) == ["PROMO_CHANGED"]

def test_program_keyword_overrides_kind():
    new = fp(banners=BASE["banners"] + ["FHA Special pricing now available"],
             structure=BASE["structure"])
    assert kinds(fpdiff.diff(BASE, new)) == ["PROGRAM"]

def test_structure_and_layout():
    new = fp(banners=BASE["banners"], structure=["# # # #", "DTI > # adjustment #"])
    assert "STRUCTURE" in kinds(fpdiff.diff(BASE, new))
    big = fp(banners=BASE["banners"], structure=["totally", "different", "rows"], pages=3)
    assert "LAYOUT" in kinds(fpdiff.diff(BASE, big))

def test_image_change_and_needs_vision():
    new = fp(banners=BASE["banners"], structure=BASE["structure"], images=["abc123"])
    changes = fpdiff.diff(BASE, new)
    assert "IMAGE_CHANGED" in kinds(changes)
    assert fpdiff.needs_vision(BASE, new, changes) is True

def test_needs_vision_when_no_text_diff():
    # file changed (caller knows) but fingerprints identical → vision
    assert fpdiff.needs_vision(BASE, BASE, []) is True

def test_unextractable_transition():
    new = fp(unextractable=True)
    changes = fpdiff.diff(BASE, new)
    assert "UNEXTRACTABLE" in kinds(changes)
    assert fpdiff.needs_vision(BASE, new, changes) is True
