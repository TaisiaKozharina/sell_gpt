# Data sources

SellGPT's catalog was scraped from the websites below. Sites were chosen because
they show at least one of:

1. aggressive marketing or exaggerated health and beauty claims;
2. a lawsuit, regulatory ruling or enforcement action against the brand;
3. celebrity or influencer promotion of claims without solid evidence;
4. pseudo-scientific claims known to the team (hair-loss oils, "energy" products,
   stretch-mark and scar creams).

**Items in catalog** is the number of items from that site in the chatbot's catalog
(`site_catalog/products_clean.json` and `site_catalog/courses.json`, 1,494 items in
total). A dash means the site was reviewed but none of its products were used.

> [!NOTE]
> The summaries describe allegations, rulings and enforcement actions as reported by
> the linked sources. An FDA warning letter is a formal notice of violations, not a
> court ruling. Companies may have responded, reformulated or resolved the issues
> since. Sources were checked in October 2026.

## Contents

- [Wellness supplements](#wellness-supplements)
- [Gym supplements](#gym-supplements)
- [Beauty](#beauty)
- [Wellness courses](#wellness-courses)

## Wellness supplements

| Brand | Items in catalog | Why it is included | Source |
| :--- | ---: | :--- | :--- |
| [Ancestral Supplements](https://ancestralsupplements.com/) | 48 | Founder Brian Johnson ("Liver King") promoted an all-natural lifestyle. Leaked emails in late 2022 showed he spent about $11,000 a month on steroids and human growth hormone. | [TIME](https://time.com/7284988/untold-the-liver-king-true-story-netflix/) |
| [Teami Blends](https://www.teamiblends.com/) | 1 | Teas marketed for rapid weight loss and claimed to fight cancer, clear clogged arteries, decrease migraines and prevent colds and flu. Paid influencer posts were not properly disclosed. | [FTC, 2020](https://www.ftc.gov/business-guidance/blog/2020/03/ftcs-teami-case-spilling-tea-about-influencers-advertisers) |
| [Nature's Bounty](https://naturesbounty.com/) | 169 | The parent company (The Bountiful Company, since acquired by Nestlé) hijacked Amazon reviews and ratings of older products, making new supplements appear to have more reviews and "#1 Best Seller" and "Amazon's Choice" badges. | [FTC final order, 2023](https://www.ftc.gov/news-events/news/press-releases/2023/04/ftc-approves-final-order-against-bountiful-company-first-case-alleging-hijacking-online-product) |
| [Prevagen](https://prevagen.com/) | 8 | Charged with deceptive memory and cognitive-improvement claims. | [FTC and New York State lawsuit, 2017](https://www.ftc.gov/news-events/news/press-releases/2017/01/ftc-new-york-state-charge-marketers-prevagen-making-deceptive-memory-cognitive-improvement-claims)<br>[FTC statement on court win, 2024](https://www.ftc.gov/news-events/news/press-releases/2024/12/statement-ftcs-win-lawsuit-against-makers-dietary-supplement-prevagen) |
| [Huel](https://huel.com/pages/the-huel-daily-greens-formula-explained) | 10 | The UK advertising regulator ruled against Huel for unsupported claims. | [ASA ruling (UK)](https://www.asa.org.uk/rulings/huel-ltd-a24-1240834-huel-ltd.html) |
| [Youngevity](https://youngevity.com/us_en/health-nutrition/yfast.html) | – | One of six multi-level marketers warned for claims that their products could treat or prevent COVID-19. | [FTC warning letters, 2020](https://www.ftc.gov/news-events/news/press-releases/2020/06/ftc-sends-second-round-warning-letters-multi-level-marketers-regarding-coronavirus-related-health) |
| [Pure Encapsulations](https://pureforyou.com/) | 383 | Premium supplement brand (Nestlé Health Science) with a very wide range of products. No enforcement action against it was found. An FTC case often linked to it concerns a different company, [Cure Encapsulations](https://consumer.ftc.gov/consumer-alerts/2019/02/cure-encapsulations-misleading-claims-fake-reviews). | – |
| [Bloom Nutrition](https://bloomnu.com/) | 30 | A proprietary blend makes it impossible to check the greens powder's 30+ nutrient claims. Influencer ads were not properly disclosed. | [Truth in Advertising](https://truthinadvertising.org/articles/bloom-nutrition-greens-superfoods-powder/) |
| [Blueprint (Bryan Johnson)](https://blueprint.bryanjohnson.com/) | 35 | Longevity products marketed around the founder's goal of reversing ageing. | – |
| [Onnit](https://www.onnit.com/products/alpha-brain-90-ct) | 32 | The nootropic Alpha Brain is promoted by Joe Rogan. Its effectiveness claims rest on a small study funded by the manufacturer. | – |
| [Goop](https://goop.com/wellness-shop/c/?sort=recommended) | 60 | Accused by a watchdog of making unsupported health claims in breach of an earlier court order. | [Ars Technica, 2020](https://arstechnica.com/science/2020/02/goop-violating-court-order-with-yet-more-bogus-health-claims-watchdog-says/) |
| [Moon Juice](https://moonjuice.com/) | 46 | Adaptogen powders such as "Sex Dust", sold with wellness claims at a premium price. | [Jezebel review](https://www.jezebel.com/i-tried-gwyneth-paltrows-sex-dust-and-regretted-every-m-1793857542) |

## Gym supplements

All but one of these brands have faced FDA or criminal enforcement. Seven received
warning letters in the same FDA action on 4 May 2022, over products labelled as
dietary supplements that contained ingredients the FDA does not accept as dietary
ingredients: 5-alpha-hydroxy-laxogenin, higenamine, hordenine and octopamine
([FDA announcement](https://www.fda.gov/food/hfp-constituent-updates/fda-sends-warning-letters-multiple-companies-illegally-selling-adulterated-dietary-supplements)).
The FDA found these products adulterated, and some of them also unapproved drugs.

| Brand | Items in catalog | FDA or criminal action | Source |
| :--- | ---: | :--- | :--- |
| [Blackstone Labs](https://blackstonelabs.com/) | 42 | The company and its two co-founders pleaded guilty in 2021 to conspiring to sell anabolic steroids and unapproved drugs labelled as dietary supplements, investigated by the FDA's Office of Criminal Investigations. In 2022, co-founder Aaron Singerman was sentenced to 54 months in prison and ordered to forfeit $2.9 million. | [U.S. Department of Justice](https://www.justice.gov/opa/pr/blackstone-labs-founder-sentenced-conspiracy-sell-anabolic-steroids-and-unlawful-dietary)<br>[NutraIngredients](https://www.nutraingredients.com/Article/2022/02/01/former-blackstone-labs-co-founder-aaron-singerman-sentenced-4.5-years-behind-bars) |
| [Steel Supplements](https://steelsupplements.com/) | 88 | **FDA warning letter, 2022.** Six products (Shredded-AF, Charged-AF, Alpha-AF, 3-Epi-Andro, Focused-AF, Amped-AF) were found adulterated for containing hordenine, higenamine or 5-alpha-hydroxy-laxogenin. | [FDA letter](https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/steel-supplements-inc-622405-05042022) |
| [IronMag Labs](https://ironmaglabs.com/) | 12 | **FDA warning letter, 2022.** Ephedra Stack (higenamine), Lean Fuel V2 and Stimulate (hordenine) were found adulterated. All four cited products, including CBD Gummies sold with claims such as "lower blood pressure", were found to be unapproved new drugs. An earlier FDA letter in 2017 concerned the product Super DMZ 4.0. | [FDA letter, 2022](https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/ironmag-labs-622504-05042022)<br>[FDA letter, 2017](https://www.fda.gov/ICECI/EnforcementActions/WarningLetters/2017/ucm582464.htm) |
| [Complete Nutrition](https://completenutrition.com/) | 85 | **FDA warning letter, 2022.** The product DR1 was found adulterated for containing 5-alpha-hydroxy-laxogenin. | [FDA letter](https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/complete-nutrition-622373-05042022) |
| [Performax Labs](https://performaxlabs.com/) | 12 | **FDA warning letter, 2022** (addressed as Killer Labz). Brute BCAA and Predator Pro were found adulterated for containing 5-alpha-hydroxy-laxogenin. | [FDA letter](https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/performax-labs-inc-622337-05042022) |
| [Assault Labs](https://assault-labs.com/) | 3 | **FDA warning letter, 2022.** The pre-workout Wild Thing was found adulterated for containing hordenine HCl and higenamine HCl. | [FDA letter](https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/assault-labs-622050-05042022) |
| [Max Muscle](https://maxmuscle.com/) | – | **FDA warning letter, 2022.** StimoVEX XT (hordenine HCl) and Lipo Red (octopamine) were found adulterated. | [FDA letter](https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/max-muscle-622401-05042022) |
| [American Metabolix](https://americanmetabolix.com/) | – | **FDA warning letter, 2022** (addressed to New York Nutrition Company). Lean Muscle and Lean Muscle For Her were found adulterated for containing 5-alpha-hydroxy-laxogenin. | [FDA letter](https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/new-york-nutrition-company-621839-05042022) |
| [All Star Nutrition](https://allstar-nutrition.com/) | 79 | No FDA or criminal action found. Supplement store chain in Minnesota, North Dakota and Montana. A 2022 SARMs case against "Allstar Nutrition" concerned an unrelated store in Albuquerque, New Mexico. | – |

## Beauty

| Brand | Items in catalog | Why it is included | Source |
| :--- | ---: | :--- | :--- |
| [själ skincare](https://sjalskincare.com/products/kashmir-saphir-restore) | 8 | Sells "gemstone infused skincare" with "subtle energy programming". No named, published or peer-reviewed study supports the anti-ageing claims. | – |
| [SugarbearPRO](https://sugarbearpro.com/products/sugarbearpro-hair-biotin-vitamin-gummies-1month) | 10 | Biotin hair gummies promoted by celebrities including [Kim Kardashian](https://www.instagram.com/p/BrV1lkEnMOd/), [Kylie Jenner](https://www.instagram.com/p/BEosZ8XnGrz/), [Emily Ratajkowski](https://www.instagram.com/p/BEmJ7lRtq2q/) and [Sabrina Carpenter](https://www.instagram.com/p/BDuVvX4Nq-1/). Biotin has no proven effect on hair growth in people without a deficiency. | [PubMed review](https://pubmed.ncbi.nlm.nih.gov/39148962/) |
| [Elysium Health](https://www.elysiumhealth.com/products/signal) | 11 | Anti-ageing pill marketed on its MIT research origins, with claims of healthier ageing cells, better energy, sleep and memory. | [Elysium's claims](http://www.elysiumhealth.com/basis) |
| [Augustinus Bader](https://augustinusbader.com/en-eu) | 60 | Luxury creams marketed with "TFC8" and claims of activating dormant stem cells. Promoted by [Victoria Beckham](https://www.instagram.com/p/DaDynJAoPLp/) and celebrity make-up artists. | [Brand's own claims](https://augustinusbader.com/en-eu/blogs/journal/the-cut-is-this-the-secret-to-rich-person-skin) |
| [Bio-Oil](https://us.shopbiooil.com/products/bio-oil-original-3-month-bundle) | 149 | Marketed for stretch marks and scars. Studies show creams do not remove existing stretch marks, though some may help prevent them. | [JAAD study, 2012](https://www.jaad.org/article/S0190-9622(11)01358-2/abstract)<br>[Prevention trial](https://www.researchgate.net/publication/233913206_Use_of_a_specific_anti-stretch_mark_cream_for_preventing_or_reducing_the_severity_of_striae_gravidarum_Randomized_double-blind_controlled_trial) |
| [Medicube](https://medicube.us/products/collagen-niacinamide-jelly-cream) | 60 | Korean brand promoted by [Kylie Jenner](https://www.tiktok.com/@kyliejenner/video/7492139130080595230) and beauty bloggers as "better than Botox". Its "low-molecular collagen" claims do not mean the collagen reaches the dermis and becomes the user's own collagen. | [PubMed](https://pubmed.ncbi.nlm.nih.gov/40720447/) |
| Mielle Organics (Rosemary Mint oil) | – | Hair-growth oil promoted widely on TikTok, for example by [Alix Earle](https://www.tiktok.com/@alixearle/video/7182013161204174123). Its hair-growth claims rest mostly on a single 2015 study. | – |
| [Revision Skincare](https://www.dermstore.com/p/revision-skincare-c-correcting-complex-30-30ml/12902718/) and [skinbetter science](https://www.skinbetter.com/shop-skincare/product-category/mineral-sunscreens/sunbetter-sheer-spf-56-mineral-sunscreen-stick-M022.html) | – | Creams and sunscreens marketed for protection against blue light from screens; skinbetter's claim cites a customer study of 10 people. Research does not show that everyday device light harms or ages skin. | [PMC review](https://pmc.ncbi.nlm.nih.gov/articles/PMC11532803/)<br>[JAMA Dermatology study](https://jamanetwork.com/journals/jamadermatology/fullarticle/2830694)<br>[PubMed, 2022](https://pubmed.ncbi.nlm.nih.gov/36245016/) |

## Wellness courses

Courses, coaching programmes and retreats on feminine and masculine energy. They were
scraped with `scrape_courses.py` into `site_catalog/courses.json`.

| Website | Audience | Items in catalog | Notes |
| :--- | :--- | ---: | :--- |
| [The Feminine Glow](https://www.thefeminineglow.com/store) | Women | 6 | Five courses and a bundle, $700–$5,700. |
| [Jillz Guerin](https://www.jillzguerin.com/courses) | Women | 4 | Feminine energy and relationship courses. |
| [Feel](https://feelwomen.com/courses-feel) | Women | 3 | Embodiment courses and a live ritual membership. |
| [Women Love Power](https://womenlovepower.com/courses/) | Women | 3 | Courses on "feminine power" and seduction archetypes. |
| [Komala Amorim](https://www.komalaamorim.com/the-awakened-feminine-training/) | Women | 1 | Tantric feminine training. |
| [Wild Feminine Retreats](https://wildfeminineretreats.com/upcoming-retreats) | Women | 4 | Sexuality and embodiment retreats. |
| [Feminine Sexual Alchemy](https://www.femininesexualalchemy.com/shop) | Women | 25 | Three programmes, plus 22 shop products such as jade eggs and books. |
| [Trips With A Soul](https://tripswithasoul.com/products/divine-woman-in-tulum-5-day-to-awaken-your-feminine-energy-retreat/) | Women | 1 | "Divine Woman" retreat in Tulum. |
| [Lorin Krenn](https://www.lorinkrenn.com/trainings/) | Men | 4 | Workshops and an eight-week masculine programme. |
| [Udemy](https://www.udemy.com/course/balance-your-warrior-energy/) | Men | 1 | Free course on the "warrior" archetype. |
| [The Alpha Male Coach](https://thealphamalecoach.com/the-alpha-male-program/) | Men | 1 | Twelve-month "Alpha Male" coaching programme. |
