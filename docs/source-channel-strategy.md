# Source Channel Strategy

This document proposes an initial set of travel-planning source channels for the new `trip-planner` design.

Two lists are included:

- a **consumer-usage shortlist** for recreational planning
- a **business-approved shortlist** for managed-travel planning

These are not universal truths. They are an initial operating set based on current market position, consumer traffic signals, and managed-travel adoption. Corporate approval varies by employer and policy.

## Consumer-Usage Top 10

Ordered by a blend of current consumer reach and usefulness for trip planning:

1. **Airbnb**
2. **Expedia**
3. **Booking.com**
4. **Vrbo**
5. **Marriott**
6. **Tripadvisor**
7. **Google Flights**
8. **Kayak**
9. **Priceline**
10. **Skyscanner**

### Why this list

- Similarweb’s latest U.S. accommodation ranking puts `airbnb.com`, `expedia.com`, `booking.com`, `vrbo.com`, and `marriott.com` in the top five accommodation/hotel destinations.
- Similarweb’s North American travel report says airlines still dominate actual flight conversions, and notes Google Flights’ growing referral influence to airline websites.
- Tripadvisor, Kayak, Priceline, and Skyscanner remain strategically important because they cover discovery, comparison, and price-shopping workflows that a leisure-planning app needs even when the final booking path lands elsewhere.

### Product Recommendation

Use this list in two tiers:

- **Discovery tier**: Tripadvisor, Google Flights, Kayak, Priceline, Skyscanner
- **Bookable inventory tier**: Airbnb, Expedia, Booking.com, Vrbo, Marriott plus direct supplier sites

For leisure mode, direct supplier sites should still be preferred when pricing parity, cancellation terms, or itinerary reliability matter.

## Business-Approved Top 10

Ordered by a blend of enterprise prevalence and suitability for policy-controlled travel programs:

1. **SAP Concur Travel**
2. **Amex GBT / Egencia**
3. **BCD Travel**
4. **Navan**
5. **CWT**
6. **FCM Travel**
7. **Corporate Travel Management (CTM)**
8. **Direct Travel**
9. **TravelPerk**
10. **Corporate Traveler**

### Why this list

- Travel Weekly’s 2025 Power List places Amex GBT, BCD Travel, Navan, and CTM among the major travel-management players.
- Business Travel News still describes the market through the influence of the historical “three megas” and highlights growing competition from newer platforms.
- Skift’s 2025 market coverage similarly points to Amex GBT and BCD as leaders and notes the rise of CTM and Navan.
- Official product materials show the kinds of policy and control capabilities this app should expect from managed-travel integrations:
  - Navan emphasizes dynamic policy controls and broad supplier inventory.
  - TravelPerk documents managed travel policies, including rental-car policy controls.
  - Amex GBT positions Egencia inside a global managed-travel platform.

### Product Recommendation

For business mode, split the source strategy into:

- **Managed-travel channels**: Concur, Amex GBT/Egencia, BCD, Navan, CWT, FCM, CTM, Direct Travel, TravelPerk, Corporate Traveler
- **Underlying supplier allowlists**: approved airlines, hotel programs, rail providers, rental-car suppliers, and ground transport services defined per policy pack

That way `trip-planner` can:

- optimize inside approved channels first
- fall back to structured alternatives only when policies allow exceptions
- preserve comparables and justification for approval review

## Integration With `Travel-Plan-Permission`

Business mode should not hardcode a single universal vendor policy.

Instead:

- `trip-planner` should maintain a default source shortlist and canonical vendor taxonomy
- `Travel-Plan-Permission` should provide organization-specific allowed vendors, preferred suppliers, caps, and exception logic
- the planner should annotate every candidate option with:
  - `source_channel`
  - `supplier`
  - `approval_status`
  - `policy_reason`
  - `comparable_reference`

## Notes On Confidence

- The top of the consumer list is higher confidence than the lower half because current Similarweb category rankings directly support it.
- The top of the business list is higher confidence than the bottom half because enterprise adoption is easier to observe for the biggest TMCs and platforms than for the long tail.
- The business list should be treated as the default seed list, then narrowed or reordered per organization.

## Reference Links

- [Similarweb: U.S. accommodation and hotels ranking](https://www.similarweb.com/top-websites/united-states/travel-and-tourism/accommodation-and-hotels/)
- [Similarweb: North American travel industry digital trends](https://www.similarweb.com/corp/reports/the-evolving-digital-state-of-the-north-american-travel-industry/)
- [Travel Weekly Power List 2025](https://www.travelweekly.com/Power-List-2025)
- [BTN CT100 2025 market overview](https://www.businesstravelnews.com/corporate-travel-100/2025/will-the-wait-and-see-approach-finally-end)
- [Skift on 2025 corporate travel market structure](https://skift.com/2025/02/20/bcd-and-amex-gbt-lead-the-corporate-travel-market-by-far-uk-regulator-reveals/)
- [Navan for Travel Managers](https://navan.com/travel-managers)
- [TravelPerk travel policy help center](https://support.travelperk.com/hc/en-us/sections/14451265665820-Managing-travel-policies)
- [Amex GBT on Egencia acquisition and platform strategy](https://www.amexglobalbusinesstravel.com/press-releases/american-express-global-business-travel-agrees-to-acquire-egencia-from-expedia-group/?highlight=Amex%2BTravel%2BCenter)
