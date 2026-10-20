"""Label every catalog item with one evaluation category.

Categories: wellness, beauty, gym, course, plus "other" for items that fit none
(merch t-shirts). Most sites sell one kind of product and are labelled by site;
the mixed sites below are labelled product by product. Items that could fairly
go either way are marked borderline so results can be checked with and without them.

Usage: python eval/label_catalog.py  ->  writes eval/product_categories.json
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOGS = [ROOT / "site_catalog" / "products_clean.json", ROOT / "site_catalog" / "courses.json"]
OUTPUT = Path(__file__).resolve().parent / "product_categories.json"

# gym = training and muscle: protein, creatine, pre-workout, workout gear, muscle recovery.
# beauty = skin, hair, nails, lashes and body care. wellness = other health products.
SITE_CATEGORY = {
    "allstar-nutrition.com": "gym", "assault-labs.com": "gym", "blackstonelabs.com": "gym",
    "completenutrition.com": "gym", "ironmaglabs.com": "gym", "performaxlabs.com": "gym",
    "steelsupplements.com": "gym",
    "augustinusbader.com": "beauty", "medicube.us": "beauty", "sjalskincare.com": "beauty",
    "us.shopbiooil.com": "beauty",
    "ancestralsupplements.com": "wellness", "blueprint.bryanjohnson.com": "wellness",
    "naturesbounty.com": "wellness", "prevagen.com": "wellness", "pureforyou.com": "wellness",
    "www.elysiumhealth.com": "wellness", "www.huel.com": "wellness",
    "www.teamiblends.com": "wellness",
}

# Mixed sites: (category, borderline) per product id suffix. Unlisted products on these
# sites fall back to the default given here.
MIXED_DEFAULT = {"goop.com": "wellness", "moonjuice.com": "wellness", "www.onnit.com": "wellness",
                 "bloomnu.com": "wellness", "sugarbearpro.com": "beauty",
                 "femininesexualalchemy.com": "wellness"}
PRODUCT_CATEGORY = {
    # goop.com: devices and body products
    "goop.com:goop-beauty-goopglow-morning-skin-superpowder": ("beauty", False),
    "goop.com:goop-beauty-g-tox-ultimate-dry-brush": ("beauty", False),
    "goop.com:necessaire-the-body-wipe": ("beauty", False),
    "goop.com:necessaire-eucalyptus-water": ("beauty", True),
    "goop.com:higherdose-microcurrent-body-sculptor-ritual-set": ("beauty", False),
    "goop.com:goop-beauty-the-martini-emotional-detox-bath-soak": ("beauty", True),
    "goop.com:the-stakt-weights": ("gym", False),
    "goop.com:bala-bangles-weighted-wrist-bangles": ("gym", False),
    "goop.com:supervibes-reformer-grip-towel": ("gym", False),
    "goop.com:therabody-theragun-mini-3-0": ("gym", True),
    "goop.com:therabody-theragun-sense": ("gym", True),
    "goop.com:therabody-recoverytherm-cube": ("gym", True),
    "goop.com:therabody-theracup": ("gym", True),
    "goop.com:full-body-red-light-mat": ("wellness", True),
    "goop.com:saunaspace-glow-infrared-therapy-light": ("wellness", True),
    # moonjuice.com: skin and hair lines; the rest are adaptogens and supplements
    "moonjuice.com:beauty-shroom-exfoliating-acid-potion": ("beauty", False),
    "moonjuice.com:acid-potion-travel-size": ("beauty", False),
    "moonjuice.com:beauty-shroom-vegan-collagen-protection": ("beauty", False),
    "moonjuice.com:cosmic-cream": ("beauty", False),
    "moonjuice.com:milk-cleanse": ("beauty", False),
    "moonjuice.com:beauty-shroom-plumping-jelly-serum": ("beauty", False),
    "moonjuice.com:high-function-basics-stack": ("beauty", False),
    "moonjuice.com:superbeauty": ("beauty", False),
    "moonjuice.com:superhair": ("beauty", False),
    "moonjuice.com:neuro-mag-superhair": ("beauty", True),
    "moonjuice.com:pearl": ("beauty", True),
    # www.onnit.com: training products; nootropics and general health stay wellness
    "www.onnit.com:alpha-brain-pre-workout-tigers-blood-20-serving-tub": ("gym", False),
    "www.onnit.com:creatine-unflavored-30-serving-tub": ("gym", False),
    "www.onnit.com:creatine-unflavored-90-serving-tub": ("gym", False),
    "www.onnit.com:grass-fed-whey-isolate-protein-mexican-chocolate-30-serving-tub": ("gym", False),
    "www.onnit.com:grass-fed-whey-isolate-protein-vanilla-30-serving-tub": ("gym", False),
    "www.onnit.com:nmn-creatine-unflavored-30-serving": ("gym", False),
    "www.onnit.com:total-nitric-oxide-harvest-fruit-20-serving-tub": ("gym", False),
    "www.onnit.com:shroom-tech-sport-28-ct": ("gym", True),
    "www.onnit.com:shroom-tech-sport-84-ct": ("gym", True),
    "www.onnit.com:brain-energy-bundle": ("wellness", True),
    # bloomnu.com: fitness line vs greens/gut/hormone line vs beauty bundles
    "bloomnu.com:brain-body-duo": ("gym", False),
    "bloomnu.com:brains-gains-set": ("gym", False),
    "bloomnu.com:clear-protein": ("gym", False),
    "bloomnu.com:clear-protein-uk": ("gym", False),
    "bloomnu.com:creatine-gummies": ("gym", False),
    "bloomnu.com:creatine": ("gym", False),
    "bloomnu.com:fitness-star-trio": ("gym", False),
    "bloomnu.com:high-energy-pre-workout": ("gym", False),
    "bloomnu.com:preworkout": ("gym", False),
    "bloomnu.com:strong-sips": ("gym", False),
    "bloomnu.com:protein": ("gym", False),
    "bloomnu.com:high-powered-mixer": ("gym", True),
    "bloomnu.com:skin-hair-transformation-trio": ("beauty", False),
    "bloomnu.com:nourish-glow-duo": ("beauty", True),
    "bloomnu.com:colostrum-collagen": ("beauty", True),
    "bloomnu.com:ultimate-gut-health-duo": ("wellness", True),
    "bloomnu.com:total-wellness-trio": ("wellness", True),
    "bloomnu.com:energy-sticks": ("wellness", True),
    # sugarbearpro.com: hair/lash/nail care, except the sleep products
    "sugarbearpro.com:sugarbear-luxury-sleep-mask": ("wellness", False),
    "sugarbearpro.com:sugarbearpro-sleep-5-htp-amino-vegan-vitamin-gummies": ("wellness", False),
    # femininesexualalchemy.com: shop items inside courses.json; the programmes are courses
    "femininesexualalchemy.com:body-guasha-tool": ("beauty", True),
    "femininesexualalchemy.com:breast-oil": ("wellness", True),
}
# Second label set, by what a product does rather than which site sells it. Covers
# only clear-cut products the chatbot actually picked in the first full run; both
# correct and wrong picks were reviewed. Ambiguous ones (electrolyte mixes, magnesium
# sprays, a multivitamin without a description) keep their site label.
FUNCTION_OVERRIDES = {
    "steelsupplements.com:focused-af-energy-mental-clarity-mood": "wellness",
    "steelsupplements.com:rested-af-rem-sleep-recovery": "wellness",
    "steelsupplements.com:immune-af": "wellness",
    "steelsupplements.com:pro-flora-probiotic": "wellness",
    "allstar-nutrition.com:essential-balance": "wellness",
    "allstar-nutrition.com:get-the-f-2-work-nootropic": "wellness",
    "allstar-nutrition.com:selfevolve-magnesium-glycinate-480-120cap": "wellness",
    "naturesbounty.com:age-defying-skin-renewal": "beauty",
    "naturesbounty.com:extra-strength-hair-skin-and-nails-5000-mcg-of-biotin-150-rapid-releaseliquid-softgels": "beauty",
    "naturesbounty.com:hair-growth-gummies": "beauty",
    "naturesbounty.com:hair-skin-and-nails-3000-mcg-of-biotin-60-coated-caplets": "beauty",
    "naturesbounty.com:ultra-collagen-booster": "beauty",
    "pureforyou.com:biotin-8-mg-60": "beauty",
    "ancestralsupplements.com:grass-fed-beef-tallow-balm": "beauty",
    "pureforyou.com:athletic-pure-pack-30": "gym",
    "pureforyou.com:muscle-cramp-tension-formula": "gym",
    "pureforyou.com:muscle-repair": "gym",
}
FUNCTION_OUTPUT = Path(__file__).resolve().parent / "product_categories_function.json"
OTHER_KEYWORDS = ("organic tee", "organic hoodie", "organic sweater", "gym top", "v-neck tee",
                  "round neck tee")


def label(item):
    """Pick a category. Parameter: catalog item dict. Return: (category, borderline)."""
    item_id, source = item["id"], item["source"]
    if item.get("category") in ("course", "retreat"):
        return "course", False
    if item_id in PRODUCT_CATEGORY:
        return PRODUCT_CATEGORY[item_id]
    if source == "femininesexualalchemy.com":
        if any(word in item["title"].lower() for word in OTHER_KEYWORDS):
            return "other", False
        if "gift card" in item["title"].lower():
            return "course", True  # a gift card for the Elixir membership programme
        return MIXED_DEFAULT[source], False
    if source in SITE_CATEGORY:
        return SITE_CATEGORY[source], False
    if source in MIXED_DEFAULT:
        return MIXED_DEFAULT[source], False
    raise KeyError(f"No category rule for {item_id} ({source})")


def main():
    """Label all catalog items and write JSON keyed by URL. Parameters: none. Return: None."""
    labels = {}
    items = [item for path in CATALOGS for item in json.loads(path.read_text(encoding="utf-8"))]
    unknown = (set(PRODUCT_CATEGORY) | set(FUNCTION_OVERRIDES)) - {item["id"] for item in items}
    if unknown:
        raise KeyError(f"Overrides that match no catalog id: {sorted(unknown)}")
    for item in items:
        category, borderline = label(item)
        labels[item["url"]] = {"category": category, "borderline": borderline,
                               "title": item["title"], "source": item["source"]}
    OUTPUT.write_text(json.dumps(labels, ensure_ascii=False, indent=1), encoding="utf-8")
    by_id = {item["id"]: item["url"] for item in items}
    function_labels = {url: dict(entry) for url, entry in labels.items()}
    for item_id, category in FUNCTION_OVERRIDES.items():
        function_labels[by_id[item_id]]["category"] = category
    FUNCTION_OUTPUT.write_text(json.dumps(function_labels, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(FUNCTION_OVERRIDES)} function-based overrides -> {FUNCTION_OUTPUT.name}")
    counts = {}
    for entry in labels.values():
        counts[entry["category"]] = counts.get(entry["category"], 0) + 1
    borderline = sum(entry["borderline"] for entry in labels.values())
    print(f"{len(labels)} items labelled: {counts}; {borderline} borderline -> {OUTPUT.name}")


if __name__ == "__main__":
    main()
